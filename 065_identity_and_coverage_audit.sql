-- Power & Corridors
-- 065_identity_and_coverage_audit.sql
-- Finds likely alternate identities and unlinked specialist/source coverage for a canonical entity.
--
-- READ-ONLY audit. No relationships are created and no records are modified.

begin;

create or replace function public.pc_model_audit_entity_coverage(p_entity_id text)
returns jsonb
language plpgsql
stable
security definer
set search_path=public
as $$
declare
    v_entity jsonb;
    v_name text;
    v_norm text;
    v_core text;
    v_result jsonb := '{}'::jsonb;
    t text;
    q text;
    rows_json jsonb;
begin
    select to_jsonb(e), e.name
      into v_entity, v_name
    from public.pc_entities e
    where e.entity_id::text=p_entity_id
    limit 1;

    if v_entity is null then
      return jsonb_build_object('entity_id',p_entity_id,'error','entity_not_found');
    end if;

    v_norm := lower(regexp_replace(coalesce(v_name,''),'[^a-zA-Z0-9]+',' ','g'));
    v_norm := trim(regexp_replace(v_norm,'\s+',' ','g'));
    v_core := trim(regexp_replace(
      v_norm,
      '\m(inc|incorporated|ltd|limited|llc|plc|company|co|group|holdings|holding)\M',
      ' ',
      'g'
    ));
    v_core := trim(regexp_replace(v_core,'\s+',' ','g'));

    v_result := jsonb_build_object(
      'entity',v_entity,
      'normalized_name',v_norm,
      'core_name',v_core
    );

    -- Exact/near duplicate entity shells.
    select coalesce(jsonb_agg(to_jsonb(x)),'[]'::jsonb)
      into rows_json
    from (
      select
        e.entity_id,e.name,e.entity_type,e.subtype,e.hq_country,e.hq_city,
        case
          when lower(regexp_replace(e.name,'[^a-zA-Z0-9]+','','g')) =
               lower(regexp_replace(v_name,'[^a-zA-Z0-9]+','','g'))
            then 'exact_normalized_name'
          when lower(e.name) like '%'||lower(v_core)||'%'
            or lower(v_core) like '%'||lower(e.name)||'%'
            then 'core_name_overlap'
          else 'other'
        end as match_reason
      from public.pc_entities e
      where e.entity_id::text<>p_entity_id
        and (
          lower(regexp_replace(e.name,'[^a-zA-Z0-9]+','','g')) =
          lower(regexp_replace(v_name,'[^a-zA-Z0-9]+','','g'))
          or (
            length(v_core)>=5
            and (
              lower(e.name) like '%'||lower(v_core)||'%'
              or lower(v_core) like '%'||lower(e.name)||'%'
            )
          )
        )
      order by e.name
      limit 100
    ) x;
    v_result := v_result || jsonb_build_object('alternate_entity_candidates',rows_json);

    -- Search likely asset identity shells by name/metadata only.
    select coalesce(jsonb_agg(to_jsonb(x)),'[]'::jsonb)
      into rows_json
    from (
      select
        a.asset_id,a.name,a.asset_type,a.subtype,a.country,a.region_city,
        a.owner_entity_id,a.operator_entity_id
      from public.pc_assets a
      where (
        length(v_core)>=5 and (
          lower(coalesce(a.name,'')) like '%'||lower(v_core)||'%'
          or lower(coalesce(a.metadata::text,'')) like '%'||lower(v_core)||'%'
        )
      )
      order by a.name
      limit 200
    ) x;
    v_result := v_result || jsonb_build_object('asset_name_candidates',rows_json);

    -- Search mobile assets where builder/yard metadata or descriptive fields contain the entity core.
    select coalesce(jsonb_agg(to_jsonb(x)),'[]'::jsonb)
      into rows_json
    from (
      select
        m.mobile_asset_id,m.name,m.asset_type,m.subtype,m.imo,m.flag,
        m.owner_entity_id,m.operator_entity_id,
        to_jsonb(m) as record
      from public.pc_mobile_assets m
      where length(v_core)>=5
        and lower(to_jsonb(m)::text) like '%'||lower(v_core)||'%'
      order by m.name
      limit 200
    ) x;
    v_result := v_result || jsonb_build_object('mobile_asset_mentions',rows_json);

    -- Dynamic textual coverage scan of specialist/source tables.
    for t in
      select unnest(array[
        'pc_defence_programmes',
        'pc_defence_programme_participants',
        'pc_shipbuilding_production_tasks',
        'pc_shipyard_capacity_history',
        'pc_shipbuilding_orders',
        'pc_company_milestones',
        'pc_events',
        'pc_documents',
        'pc_transactions',
        'pc_projects',
        'pc_project_details'
      ])
    loop
      if to_regclass('public.'||t) is not null and length(v_core)>=5 then
        q := format(
          'select coalesce(jsonb_agg(x),''[]''::jsonb) from (
             select to_jsonb(r) x
             from public.%I r
             where lower(to_jsonb(r)::text) like $1
             limit 100
           ) s',
          t
        );
        execute q into rows_json using '%'||lower(v_core)||'%';
        v_result := v_result || jsonb_build_object(t,coalesce(rows_json,'[]'::jsonb));
      end if;
    end loop;

    -- All explicit inbound/outbound graph edges for comparison.
    select coalesce(jsonb_agg(to_jsonb(r)),'[]'::jsonb)
      into rows_json
    from public.pc_relationships r
    where (lower(coalesce(r.source_type,''))='entity' and r.source_id::text=p_entity_id)
       or (lower(coalesce(r.target_type,''))='entity' and r.target_id::text=p_entity_id);
    v_result := v_result || jsonb_build_object('generic_relationships',rows_json);

    return v_result;
end;
$$;

grant execute on function public.pc_model_audit_entity_coverage(text) to authenticated,service_role,postgres;


-- Bulk list of entities that are likely under-linked despite having textual/specialist coverage.
create or replace view public.pc_v_underlinked_entity_candidates as
select
  c.entity_id,
  c.name,
  c.entity_type,
  c.subtype,
  c.country,
  c.total_known_connections,
  c.generic_relationships,
  c.company_asset_roles,
  c.direct_fixed_asset_refs,
  c.direct_mobile_asset_refs,
  c.event_links,
  c.document_links,
  c.defence_programme_links,
  c.production_links,
  c.shipyard_capacity_links,
  c.security_operation_links,
  case
    when c.total_known_connections=0 then 'zero_connection_entity'
    when c.rich_but_missing_generic_graph then 'specialist_data_not_in_generic_graph'
    when c.total_known_connections<=2 then 'very_thin_entity'
    else 'connected'
  end as audit_bucket
from public.pc_v_entity_relationship_coverage c
where c.total_known_connections=0
   or c.rich_but_missing_generic_graph
   or c.total_known_connections<=2;

grant select on public.pc_v_underlinked_entity_candidates to authenticated,service_role;

commit;

-- Suggested:
-- select public.pc_model_audit_entity_coverage('COMP_IRVING');
-- select * from public.pc_v_underlinked_entity_candidates
-- where lower(name) like '%seaspan%' or lower(name) like '%irving%';
-- select audit_bucket,count(*) from public.pc_v_underlinked_entity_candidates group by audit_bucket;
