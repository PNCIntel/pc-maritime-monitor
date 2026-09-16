-- Power & Corridors
-- 054_fix_deferred_canonical_apply.sql
-- Fixes deferred participant/event-link writes and exposes exact SQL errors.
-- Replaces pc_apply_deferred_canonical_job_v1 from migration 053.
-- Safe to run repeatedly.

begin;

create or replace function pc_apply_deferred_canonical_job_v1(
    p_ingestion_job_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    r record;
    p jsonb;
    v_tx text;
    v_entity text;
    v_event text;
    v_linked text;
    v_source_id text;
    v_event_link_id text;
    v_existing text;
    v_role text;
    v_event_meta jsonb;
    v_tx_meta jsonb;
    v_new_event_links jsonb;
    v_new_tx_links jsonb;
    v_applied integer := 0;
    v_review integer := 0;
    v_participants integer := 0;
    v_event_links integer := 0;
    v_bridges integer := 0;
    v_errors jsonb := '[]'::jsonb;
begin
    for r in
        select *
          from pc_staged_records
         where ingestion_job_id=p_ingestion_job_id
           and target_table in ('pc_transaction_participants','pc_event_links')
           and lower(coalesce(review_status,'')) <> 'applied'
         order by created_at, staged_record_id
    loop
        p := coalesce(r.payload,'{}'::jsonb);

        begin
            -- ===============================================================
            -- TRANSACTION PARTICIPANTS
            -- ===============================================================
            if r.target_table='pc_transaction_participants' then
                v_tx := pc_resolve_package_object_id_v1(
                    p_ingestion_job_id,'transaction',p->>'transaction_id'
                );
                if v_tx is null then
                    raise exception 'transaction_id % does not resolve canonically',
                        p->>'transaction_id';
                end if;

                v_role := nullif(p->>'role','');
                if v_role is null then
                    raise exception 'participant role is required';
                end if;

                if not exists(
                    select 1
                      from pc_meta_transaction_participant_roles
                     where role=v_role
                       and active=true
                ) then
                    raise exception 'participant role % is not registered/active',v_role;
                end if;

                v_entity := null;
                if nullif(p->>'entity_id','') is not null then
                    v_entity := pc_resolve_package_object_id_v1(
                        p_ingestion_job_id,'entity',p->>'entity_id'
                    );
                    -- entity_id is nullable in the live model. Preserve the name even
                    -- if a named party is not yet canonical rather than blocking load.
                end if;

                v_source_id := nullif(p->>'source_id','');
                if v_source_id is not null
                   and not exists(select 1 from pc_sources where source_id=v_source_id)
                then
                    v_source_id := null;
                end if;

                insert into pc_transaction_participants(
                    participant_id,
                    transaction_id,
                    entity_id,
                    participant_name,
                    role,
                    ownership_percent,
                    lead_participant,
                    valid_from,
                    valid_to,
                    source_id,
                    notes,
                    metadata
                )
                values(
                    p->>'participant_id',
                    v_tx,
                    v_entity,
                    nullif(p->>'participant_name',''),
                    v_role,
                    case when nullif(p->>'ownership_percent','') is null
                         then null else (p->>'ownership_percent')::numeric end,
                    case when nullif(p->>'lead_participant','') is null
                         then false else (p->>'lead_participant')::boolean end,
                    case when nullif(p->>'valid_from','') is null
                         then null else (p->>'valid_from')::date end,
                    case when nullif(p->>'valid_to','') is null
                         then null else (p->>'valid_to')::date end,
                    v_source_id,
                    nullif(p->>'notes',''),
                    coalesce(p->'metadata','{}'::jsonb)
                    || case
                         when nullif(p->>'entity_id','') is not null and v_entity is null
                         then jsonb_build_object('unresolved_package_entity_id',p->>'entity_id')
                         else '{}'::jsonb
                       end
                )
                on conflict (participant_id) do update set
                    transaction_id    = excluded.transaction_id,
                    entity_id         = excluded.entity_id,
                    participant_name  = excluded.participant_name,
                    role              = excluded.role,
                    ownership_percent = excluded.ownership_percent,
                    lead_participant  = excluded.lead_participant,
                    valid_from        = excluded.valid_from,
                    valid_to          = excluded.valid_to,
                    source_id         = excluded.source_id,
                    notes             = excluded.notes,
                    metadata          = coalesce(pc_transaction_participants.metadata,'{}'::jsonb)
                                        || excluded.metadata;

                -- Do NOT write transaction_id / participant_id into resolved_entity_id.
                -- That field is semantically for canonical object resolution, not child rows.
                update pc_staged_records set
                    review_status='applied',
                    validation_status='reviewed',
                    resolution_status='READY',
                    resolution_method='sql_v21_transaction_participant_apply',
                    resolution_confidence=1.0,
                    candidate_count=1,
                    resolved_entity_id=null,
                    resolution_details=jsonb_build_object(
                        'canonical_transaction_id',v_tx,
                        'canonical_entity_id',v_entity,
                        'participant_id',p->>'participant_id'
                    )
                 where staged_record_id=r.staged_record_id;

                v_applied:=v_applied+1;
                v_participants:=v_participants+1;
                continue;
            end if;

            -- ===============================================================
            -- EVENT LINKS / TRANSACTION BRIDGE
            -- ===============================================================
            if r.target_table='pc_event_links' then
                v_event := pc_resolve_package_object_id_v1(
                    p_ingestion_job_id,'event',p->>'event_id'
                );
                if v_event is null then
                    raise exception 'event_id % does not resolve canonically',p->>'event_id';
                end if;

                -- Transaction is not a native pc_event_links endpoint in the current
                -- model. Store a source-linked bidirectional semantic bridge instead.
                if lower(coalesce(p->>'linked_type','')) in ('transaction','deal') then
                    v_linked := pc_resolve_package_object_id_v1(
                        p_ingestion_job_id,'transaction',p->>'linked_id'
                    );
                    if v_linked is null then
                        raise exception 'transaction % does not resolve canonically',p->>'linked_id';
                    end if;

                    select coalesce(metadata,'{}'::jsonb)
                      into v_event_meta
                      from pc_events
                     where event_id=v_event;

                    select coalesce(metadata,'{}'::jsonb)
                      into v_tx_meta
                      from pc_transactions
                     where transaction_id=v_linked;

                    select coalesce(jsonb_agg(x order by x),'[]'::jsonb)
                      into v_new_event_links
                      from (
                            select distinct value as x
                              from jsonb_array_elements_text(
                                  coalesce(v_event_meta->'linked_transaction_ids','[]'::jsonb)
                              )
                            union
                            select v_linked
                           ) q;

                    select coalesce(jsonb_agg(x order by x),'[]'::jsonb)
                      into v_new_tx_links
                      from (
                            select distinct value as x
                              from jsonb_array_elements_text(
                                  coalesce(v_tx_meta->'linked_event_ids','[]'::jsonb)
                              )
                            union
                            select v_event
                           ) q;

                    update pc_events
                       set metadata =
                           coalesce(metadata,'{}'::jsonb)
                           || jsonb_build_object(
                                'linked_transaction_ids',v_new_event_links,
                                'transaction_link_method','canonical_metadata_bridge'
                              )
                     where event_id=v_event;

                    update pc_transactions
                       set metadata =
                           coalesce(metadata,'{}'::jsonb)
                           || jsonb_build_object(
                                'linked_event_ids',v_new_tx_links,
                                'event_link_method','canonical_metadata_bridge'
                              )
                     where transaction_id=v_linked;

                    update pc_staged_records set
                        review_status='applied',
                        validation_status='reviewed',
                        resolution_status='READY',
                        resolution_method='sql_v21_event_transaction_bridge',
                        resolution_confidence=1.0,
                        candidate_count=1,
                        resolved_entity_id=null,
                        resolution_details=jsonb_build_object(
                            'canonical_event_id',v_event,
                            'canonical_transaction_id',v_linked
                        )
                     where staged_record_id=r.staged_record_id;

                    v_applied:=v_applied+1;
                    v_bridges:=v_bridges+1;
                    continue;
                end if;

                v_linked := pc_resolve_package_object_id_v1(
                    p_ingestion_job_id,p->>'linked_type',p->>'linked_id'
                );
                if v_linked is null then
                    raise exception 'linked endpoint %:% does not resolve canonically',
                        p->>'linked_type',p->>'linked_id';
                end if;

                v_source_id := nullif(p->>'source_id','');
                if v_source_id is not null
                   and not exists(select 1 from pc_sources where source_id=v_source_id)
                then
                    v_source_id := null;
                end if;

                select event_link_id
                  into v_existing
                  from pc_event_links
                 where event_id=v_event
                   and linked_type=p->>'linked_type'
                   and linked_id=v_linked
                   and relationship=p->>'relationship'
                 limit 1;

                v_event_link_id := coalesce(
                    v_existing,
                    nullif(p->>'event_link_id',''),
                    'EVL_' || upper(substr(md5(
                        v_event || '|' ||
                        coalesce(p->>'linked_type','') || '|' ||
                        v_linked || '|' ||
                        coalesce(p->>'relationship','')
                    ),1,24))
                );

                insert into pc_event_links(
                    event_link_id,
                    event_id,
                    linked_type,
                    linked_id,
                    linked_name,
                    relationship,
                    confidence,
                    source_id,
                    metadata
                )
                values(
                    v_event_link_id,
                    v_event,
                    p->>'linked_type',
                    v_linked,
                    nullif(p->>'linked_name',''),
                    p->>'relationship',
                    nullif(p->>'confidence',''),
                    v_source_id,
                    coalesce(p->'metadata','{}'::jsonb)
                )
                on conflict (event_link_id) do update set
                    event_id      = excluded.event_id,
                    linked_type   = excluded.linked_type,
                    linked_id     = excluded.linked_id,
                    linked_name   = excluded.linked_name,
                    relationship  = excluded.relationship,
                    confidence    = excluded.confidence,
                    source_id     = excluded.source_id,
                    metadata      = coalesce(pc_event_links.metadata,'{}'::jsonb)
                                    || excluded.metadata;

                update pc_staged_records set
                    review_status='applied',
                    validation_status='reviewed',
                    resolution_status='READY',
                    resolution_method='sql_v21_event_link_apply',
                    resolution_confidence=1.0,
                    candidate_count=1,
                    resolved_entity_id=null,
                    resolution_details=jsonb_build_object(
                        'canonical_event_id',v_event,
                        'canonical_linked_id',v_linked,
                        'event_link_id',v_event_link_id
                    )
                 where staged_record_id=r.staged_record_id;

                v_applied:=v_applied+1;
                v_event_links:=v_event_links+1;
                continue;
            end if;

        exception when others then
            update pc_staged_records set
                review_status='pending',
                validation_status='needs_review',
                resolution_status='BROKEN_REFERENCE',
                resolution_method='sql_v21_deferred_apply_error',
                resolved_entity_id=null,
                resolution_details=jsonb_build_object(
                    'reason',sqlerrm,
                    'sqlstate',sqlstate,
                    'target_table',r.target_table,
                    'natural_key',r.natural_key
                )
             where staged_record_id=r.staged_record_id;

            v_review:=v_review+1;
            v_errors:=v_errors || jsonb_build_array(
                jsonb_build_object(
                    'target_table',r.target_table,
                    'natural_key',r.natural_key,
                    'sqlstate',sqlstate,
                    'reason',sqlerrm
                )
            );
        end;
    end loop;

    return jsonb_build_object(
        'applied',v_applied,
        'review',v_review,
        'participants_applied',v_participants,
        'event_links_applied',v_event_links,
        'transaction_bridges_applied',v_bridges,
        'errors',v_errors
    );
end;
$$;

revoke all on function pc_apply_deferred_canonical_job_v1(uuid) from public;
grant execute on function pc_apply_deferred_canonical_job_v1(uuid)
to authenticated, service_role;

commit;

-- Optional diagnostic for the most recent unresolved rows:
select
    target_table,
    natural_key,
    resolution_method,
    resolution_details->>'sqlstate' as sqlstate,
    resolution_details->>'reason' as exact_reason
from pc_staged_records
where review_status <> 'applied'
order by created_at desc
limit 50;
