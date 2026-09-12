-- Power & Corridors Trade System
-- 024_mobile_asset_relationship_completion.sql
-- Ensures researched vessels/mobile assets do not remain orphaned from the company graph.
-- Staging only: creates pc_relationships proposals and resolves endpoints; canonical apply remains separate.

begin;

create or replace view pc_v_population_mobile_asset_coverage as
with mobiles as (
    select
        s.ingestion_job_id,
        s.staged_record_id,
        s.natural_key,
        coalesce(nullif(s.payload->>'name',''), s.natural_key) as mobile_asset_name,
        coalesce(s.resolved_entity_id, s.payload->>'mobile_asset_id') as mobile_asset_id,
        coalesce(nullif(s.payload->>'asset_type',''), nullif(s.payload->>'vessel_type','')) as asset_type,
        nullif(s.payload->>'imo','') as imo,
        coalesce(s.resolution_status,'UNRESOLVED') as identity_status,
        s.confidence,
        s.source_id,
        coalesce(s.payload->'metadata','{}'::jsonb) as metadata
    from pc_staged_records s
    where s.target_table='pc_mobile_assets'
      and coalesce(s.review_status,'pending') <> 'rejected'
),
rels as (
    select
        sr.ingestion_job_id,
        sr.staged_relationship_id,
        sr.relationship_type,
        sr.from_name,
        sr.to_name,
        sr.resolved_from_entity_id,
        sr.resolved_to_entity_id,
        sr.resolution_status,
        sr.apply_status
    from pc_staged_relationships sr
    where sr.from_entity_type='entity'
      and sr.to_entity_type='mobile_asset'
)
select
    m.*,
    r.staged_relationship_id,
    r.relationship_type,
    r.from_name as company_name,
    r.resolved_from_entity_id as company_id,
    r.resolution_status as relationship_status,
    r.apply_status,
    (r.staged_relationship_id is not null) as has_company_link
from mobiles m
left join lateral (
    select r.*
    from rels r
    where r.ingestion_job_id=m.ingestion_job_id
      and (
            (m.mobile_asset_id is not null and r.resolved_to_entity_id=m.mobile_asset_id)
         or pc_normalize_name(r.to_name)=pc_normalize_name(m.mobile_asset_name)
      )
    order by
        case when r.resolution_status='READY' then 0
             when r.resolution_status='ALREADY_EXISTS' then 1
             when r.resolution_status='PARTIAL' then 2
             else 3 end,
        r.staged_relationship_id
    limit 1
) r on true;


create or replace function pc_stage_missing_mobile_asset_links(
    p_ingestion_job_id uuid,
    p_company_name text,
    p_relationship_type text default 'operates'
)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    r record;
    v_payload jsonb;
    v_natural_key text;
    v_staged_record_id uuid;
    v_staged_relationship_id uuid;
    v_resolution jsonb;
    v_total integer := 0;
    v_staged integer := 0;
    v_skipped_existing integer := 0;
    v_skipped_no_source integer := 0;
    v_rel text;
begin
    if p_ingestion_job_id is null then
        raise exception 'p_ingestion_job_id is required';
    end if;
    if coalesce(trim(p_company_name),'')='' then
        raise exception 'p_company_name is required';
    end if;

    v_rel := lower(trim(coalesce(p_relationship_type,'operates')));
    if v_rel not in ('operates','owns','manages','charters') then
        raise exception 'Unsupported mobile asset relationship_type: %',v_rel;
    end if;

    for r in
        select *
        from pc_v_population_mobile_asset_coverage
        where ingestion_job_id=p_ingestion_job_id
        order by mobile_asset_name
    loop
        v_total := v_total + 1;

        if r.has_company_link then
            v_skipped_existing := v_skipped_existing + 1;
            continue;
        end if;

        -- Require source-backed mobile asset evidence before creating a fleet link.
        if coalesce(jsonb_array_length(
            case
                when jsonb_typeof(r.metadata->'research_sources')='array'
                then r.metadata->'research_sources'
                else '[]'::jsonb
            end
        ),0)=0 and r.source_id is null then
            v_skipped_no_source := v_skipped_no_source + 1;
            continue;
        end if;

        v_natural_key :=
            'fleet_' ||
            regexp_replace(pc_normalize_name(p_company_name),'[^a-z0-9]+','_','g') ||
            '_' || v_rel || '_' ||
            regexp_replace(pc_normalize_name(r.mobile_asset_name),'[^a-z0-9]+','_','g');

        v_payload := jsonb_strip_nulls(jsonb_build_object(
            'source_type','entity',
            'source_name',p_company_name,
            'relationship_type',v_rel,
            'target_type','mobile_asset',
            'target_name',r.mobile_asset_name,
            'target_id',r.mobile_asset_id,
            'evidence_source_id',r.source_id,
            'metadata',coalesce(r.metadata,'{}'::jsonb) || jsonb_build_object(
                'relationship_family','fleet',
                'generated_from_mobile_asset_staging',true,
                'source_mobile_staged_record_id',r.staged_record_id
            )
        ));

        select staged_record_id
          into v_staged_record_id
          from pc_staged_records
         where ingestion_job_id=p_ingestion_job_id
           and target_table='pc_relationships'
           and natural_key=v_natural_key
           and coalesce(review_status,'pending') not in ('rejected','applied')
         order by created_at desc
         limit 1;

        if v_staged_record_id is null then
            insert into pc_staged_records(
                ingestion_job_id,target_table,source_record_key,natural_key,action,payload,
                confidence,validation_status,review_status,resolution_status
            )
            values (
                p_ingestion_job_id,'pc_relationships',v_natural_key,v_natural_key,'REVIEW',v_payload,
                coalesce(r.confidence,0.95),'pending','pending','UNRESOLVED'
            )
            returning staged_record_id into v_staged_record_id;
        else
            update pc_staged_records
               set payload=v_payload,
                   validation_status='pending',
                   review_status='pending',
                   resolution_status='UNRESOLVED'
             where staged_record_id=v_staged_record_id;
        end if;

        v_staged_relationship_id := pc_stage_generic_relationship(v_staged_record_id);
        v_resolution := pc_resolve_generic_relationship(v_staged_relationship_id);
        v_staged := v_staged + 1;
    end loop;

    return jsonb_build_object(
        'job_id',p_ingestion_job_id,
        'company_name',p_company_name,
        'relationship_type',v_rel,
        'mobile_assets_seen',v_total,
        'fleet_links_staged',v_staged,
        'skipped_existing_link',v_skipped_existing,
        'skipped_no_source',v_skipped_no_source
    );
end;
$$;


create or replace function pc_population_mobile_asset_stats(
    p_ingestion_job_id uuid
)
returns jsonb
language sql
security definer
set search_path=public
as $$
    select jsonb_build_object(
        'mobile_assets',count(*),
        'linked',count(*) filter (where has_company_link),
        'unlinked',count(*) filter (where not has_company_link),
        'ready_links',count(*) filter (where relationship_status='READY'),
        'partial_links',count(*) filter (where relationship_status='PARTIAL'),
        'existing_links',count(*) filter (where relationship_status='ALREADY_EXISTS')
    )
    from pc_v_population_mobile_asset_coverage
    where ingestion_job_id=p_ingestion_job_id;
$$;

comment on view pc_v_population_mobile_asset_coverage is
'Per-population-job vessel/mobile-asset coverage showing whether each staged mobile asset has a company graph link.';

comment on function pc_stage_missing_mobile_asset_links(uuid,text,text) is
'Stages source-backed company-to-mobile-asset fleet relationships for orphaned staged mobile assets, then invokes generic endpoint resolution. Canonical apply remains separate.';

comment on function pc_population_mobile_asset_stats(uuid) is
'Returns mobile-asset coverage counts for one research population job.';

commit;
