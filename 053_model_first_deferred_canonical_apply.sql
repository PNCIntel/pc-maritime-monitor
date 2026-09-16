-- Power & Corridors
-- 053_model_first_deferred_canonical_apply.sql
-- Canonical Loader V20 backend support
--
-- Purpose
-- -------
-- Apply child / graph rows only AFTER canonical parent objects have been resolved.
-- Runs SECURITY DEFINER so the canonical loader does not need direct RLS write
-- privileges on pc_transaction_participants, pc_relationships or pc_event_links.
--
-- Safe to run repeatedly.

begin;

-- ---------------------------------------------------------------------------
-- Baseline controlled vocabulary required by transaction participants.
-- ---------------------------------------------------------------------------

insert into pc_meta_transaction_participant_roles
    (role, display_name, role_group, description, active, metadata)
values
    ('buyer',       'Buyer / Acquirer',         'acquirer',    'Purchasing or acquiring party.', true, '{"system_baseline":true}'::jsonb),
    ('seller',      'Seller / Disposing Party', 'seller',      'Selling or disposing party.', true, '{"system_baseline":true}'::jsonb),
    ('target',      'Target',                    'target',      'Company, asset or business that is the subject of the transaction.', true, '{"system_baseline":true}'::jsonb),
    ('offeror',     'Offeror',                   'acquirer',    'Party making a tender, takeover or other formal offer.', true, '{"system_baseline":true}'::jsonb),
    ('shareholder', 'Shareholder',               'shareholder', 'Shareholder participating in or affected by the transaction.', true, '{"system_baseline":true}'::jsonb),
    ('sponsor',     'Sponsor / Parent',          'sponsor',     'Parent, sponsor or controlling party backing the transaction.', true, '{"system_baseline":true}'::jsonb),
    ('advisor',     'Advisor',                   'advisor',     'Financial, legal or other transaction adviser.', true, '{"system_baseline":true}'::jsonb),
    ('financier',   'Financier',                 'financier',   'Debt or equity financing provider.', true, '{"system_baseline":true}'::jsonb)
on conflict (role) do update set
    display_name = excluded.display_name,
    role_group   = excluded.role_group,
    description  = excluded.description,
    active       = true,
    metadata     = coalesce(pc_meta_transaction_participant_roles.metadata,'{}'::jsonb) || excluded.metadata,
    updated_at   = now();

-- Common vessel ownership/management graph semantics used by fleet research packages.
insert into pc_meta_relationship_types
    (relationship_type, from_entity_type, to_entity_type, relationship_table,
     from_key_column, to_key_column, relationship_type_column,
     inverse_relationship_type, cardinality, active, description, metadata)
values
    ('owns',                 'entity', 'mobile_asset', 'pc_relationships', 'source_id', 'target_id', 'relationship_type', 'owned_by',                  'one_to_many', true, 'Entity owns a mobile asset.', '{"system_baseline":true}'::jsonb),
    ('commercially_manages', 'entity', 'mobile_asset', 'pc_relationships', 'source_id', 'target_id', 'relationship_type', 'commercially_managed_by', 'one_to_many', true, 'Entity commercially manages a mobile asset.', '{"system_baseline":true}'::jsonb),
    ('technically_manages',  'entity', 'mobile_asset', 'pc_relationships', 'source_id', 'target_id', 'relationship_type', 'technically_managed_by',  'one_to_many', true, 'Entity technically / ISM manages a mobile asset.', '{"system_baseline":true}'::jsonb)
on conflict (relationship_type) do update set
    active = true,
    description = excluded.description,
    metadata = coalesce(pc_meta_relationship_types.metadata,'{}'::jsonb) || excluded.metadata;

-- ---------------------------------------------------------------------------
-- Helper: resolve a package-local object ID to its canonical database ID.
-- ---------------------------------------------------------------------------

create or replace function pc_resolve_package_object_id_v1(
    p_job uuid,
    p_object_type text,
    p_package_id text
)
returns text
language plpgsql
security definer
set search_path = public
as $$
declare
    v_id text;
    v_imo text;
begin
    if p_package_id is null or btrim(p_package_id) = '' then
        return null;
    end if;

    case lower(p_object_type)
    when 'entity' then
        if exists(select 1 from pc_entities where entity_id=p_package_id) then
            return p_package_id;
        end if;

        select coalesce(nullif(resolved_entity_id,''), payload->>'entity_id')
          into v_id
          from pc_staged_records
         where ingestion_job_id=p_job
           and target_table='pc_entities'
           and payload->>'entity_id'=p_package_id
           and lower(coalesce(review_status,''))='applied'
         order by created_at desc
         limit 1;

        if v_id is not null and exists(select 1 from pc_entities where entity_id=v_id) then
            return v_id;
        end if;

        select e.entity_id
          into v_id
          from pc_staged_records s
          join pc_entities e on lower(btrim(e.name))=lower(btrim(s.payload->>'name'))
         where s.ingestion_job_id=p_job
           and s.target_table='pc_entities'
           and s.payload->>'entity_id'=p_package_id
         limit 1;
        return v_id;

    when 'mobile_asset' then
        if exists(select 1 from pc_mobile_assets where mobile_asset_id=p_package_id) then
            return p_package_id;
        end if;

        select nullif(resolved_entity_id,''),
               nullif(payload->>'imo','')
          into v_id, v_imo
          from pc_staged_records
         where ingestion_job_id=p_job
           and target_table='pc_mobile_assets'
           and payload->>'mobile_asset_id'=p_package_id
         order by created_at desc
         limit 1;

        if v_id is not null and exists(select 1 from pc_mobile_assets where mobile_asset_id=v_id) then
            return v_id;
        end if;

        if v_imo is not null then
            select mobile_asset_id into v_id
              from pc_mobile_assets
             where imo=v_imo
             limit 1;
            return v_id;
        end if;
        return null;

    when 'asset' then
        if exists(select 1 from pc_assets where asset_id=p_package_id) then
            return p_package_id;
        end if;
        select coalesce(nullif(resolved_entity_id,''), payload->>'asset_id')
          into v_id
          from pc_staged_records
         where ingestion_job_id=p_job
           and target_table='pc_assets'
           and payload->>'asset_id'=p_package_id
           and lower(coalesce(review_status,''))='applied'
         order by created_at desc
         limit 1;
        if v_id is not null and exists(select 1 from pc_assets where asset_id=v_id) then
            return v_id;
        end if;
        return null;

    when 'event' then
        if exists(select 1 from pc_events where event_id=p_package_id) then
            return p_package_id;
        end if;
        select payload->>'event_id'
          into v_id
          from pc_staged_records
         where ingestion_job_id=p_job
           and target_table='pc_events'
           and payload->>'event_id'=p_package_id
         limit 1;
        if v_id is not null and exists(select 1 from pc_events where event_id=v_id) then
            return v_id;
        end if;
        return null;

    when 'transaction', 'deal' then
        if exists(select 1 from pc_transactions where transaction_id=p_package_id) then
            return p_package_id;
        end if;
        select payload->>'transaction_id'
          into v_id
          from pc_staged_records
         where ingestion_job_id=p_job
           and target_table='pc_transactions'
           and payload->>'transaction_id'=p_package_id
         limit 1;
        if v_id is not null and exists(select 1 from pc_transactions where transaction_id=v_id) then
            return v_id;
        end if;
        return null;

    else
        return null;
    end case;
end;
$$;

-- ---------------------------------------------------------------------------
-- Deferred child/graph processor.
-- ---------------------------------------------------------------------------

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
    v_source text;
    v_target text;
    v_rel_id text;
    v_event_link_id text;
    v_existing text;
    v_role text;
    v_event_meta jsonb;
    v_tx_meta jsonb;
    v_applied integer := 0;
    v_review integer := 0;
    v_participants integer := 0;
    v_relationships integer := 0;
    v_event_links integer := 0;
    v_bridges integer := 0;
begin
    for r in
        select *
          from pc_staged_records
         where ingestion_job_id=p_ingestion_job_id
           and target_table in ('pc_transaction_participants','pc_relationships','pc_event_links')
           and lower(coalesce(review_status,'')) <> 'applied'
         order by created_at, staged_record_id
    loop
        p := coalesce(r.payload,'{}'::jsonb);

        begin
            -- ---------------------------------------------------------------
            -- TRANSACTION PARTICIPANTS
            -- ---------------------------------------------------------------
            if r.target_table='pc_transaction_participants' then
                v_tx := pc_resolve_package_object_id_v1(
                    p_ingestion_job_id,'transaction',p->>'transaction_id'
                );
                if v_tx is null then
                    raise exception 'transaction_id % does not resolve canonically', p->>'transaction_id';
                end if;

                v_role := nullif(p->>'role','');
                if v_role is null or not exists(
                    select 1 from pc_meta_transaction_participant_roles
                     where role=v_role and active=true
                ) then
                    raise exception 'participant role % is not registered/active', v_role;
                end if;

                v_entity := null;
                if nullif(p->>'entity_id','') is not null then
                    v_entity := pc_resolve_package_object_id_v1(
                        p_ingestion_job_id,'entity',p->>'entity_id'
                    );
                end if;

                insert into pc_transaction_participants(
                    participant_id, transaction_id, entity_id, participant_name, role,
                    ownership_percent, lead_participant, valid_from, valid_to,
                    source_id, notes, metadata
                )
                values(
                    p->>'participant_id',
                    v_tx,
                    v_entity,
                    nullif(p->>'participant_name',''),
                    v_role,
                    nullif(p->>'ownership_percent','')::numeric,
                    coalesce(nullif(p->>'lead_participant','')::boolean,false),
                    nullif(p->>'valid_from','')::date,
                    nullif(p->>'valid_to','')::date,
                    nullif(p->>'source_id',''),
                    nullif(p->>'notes',''),
                    coalesce(p->'metadata','{}'::jsonb)
                )
                on conflict (participant_id) do update set
                    transaction_id=excluded.transaction_id,
                    entity_id=excluded.entity_id,
                    participant_name=excluded.participant_name,
                    role=excluded.role,
                    ownership_percent=excluded.ownership_percent,
                    lead_participant=excluded.lead_participant,
                    valid_from=excluded.valid_from,
                    valid_to=excluded.valid_to,
                    source_id=excluded.source_id,
                    notes=excluded.notes,
                    metadata=coalesce(pc_transaction_participants.metadata,'{}'::jsonb) || excluded.metadata;

                update pc_staged_records set
                    review_status='applied',
                    validation_status='reviewed',
                    resolution_status='READY',
                    resolution_method='sql_v20_transaction_participant_apply',
                    resolution_confidence=1.0,
                    candidate_count=1,
                    resolved_entity_id=coalesce(v_entity,v_tx),
                    resolution_details=jsonb_build_object(
                        'canonical_transaction_id',v_tx,
                        'canonical_entity_id',v_entity
                    )
                 where staged_record_id=r.staged_record_id;

                v_applied:=v_applied+1;
                v_participants:=v_participants+1;
                continue;
            end if;

            -- ---------------------------------------------------------------
            -- GENERIC RELATIONSHIPS
            -- ---------------------------------------------------------------
            if r.target_table='pc_relationships' then
                v_source := pc_resolve_package_object_id_v1(
                    p_ingestion_job_id,p->>'source_type',p->>'source_id'
                );
                v_target := pc_resolve_package_object_id_v1(
                    p_ingestion_job_id,p->>'target_type',p->>'target_id'
                );

                if v_source is null or v_target is null then
                    raise exception 'relationship endpoints unresolved: %:% -> %, %:% -> %',
                        p->>'source_type',p->>'source_id',v_source,
                        p->>'target_type',p->>'target_id',v_target;
                end if;

                select relationship_id into v_existing
                  from pc_relationships
                 where source_type=p->>'source_type'
                   and source_id=v_source
                   and relationship_type=p->>'relationship_type'
                   and target_type=p->>'target_type'
                   and target_id=v_target
                 limit 1;

                if v_existing is not null then
                    v_rel_id:=v_existing;
                elsif coalesce(p->>'relationship_id','')='' or p->>'relationship_id' like 'PKG_%' then
                    v_rel_id:='REL_' || upper(substr(md5(
                        coalesce(p->>'source_type','') || '|' || v_source || '|' ||
                        coalesce(p->>'relationship_type','') || '|' ||
                        coalesce(p->>'target_type','') || '|' || v_target
                    ),1,24));
                else
                    v_rel_id:=p->>'relationship_id';
                end if;

                insert into pc_relationships(
                    relationship_id, source_type, source_id, relationship_type,
                    target_type, target_id, ownership_percent, operating_control,
                    valid_from, valid_to, confidence, record_status,
                    evidence_source_id, notes, source_url, metadata
                )
                values(
                    v_rel_id,
                    p->>'source_type',
                    v_source,
                    p->>'relationship_type',
                    p->>'target_type',
                    v_target,
                    nullif(p->>'ownership_percent','')::numeric,
                    nullif(p->>'operating_control','')::boolean,
                    nullif(p->>'valid_from','')::date,
                    nullif(p->>'valid_to','')::date,
                    nullif(p->>'confidence',''),
                    coalesce(nullif(p->>'record_status',''),'provisional'),
                    nullif(p->>'evidence_source_id',''),
                    nullif(p->>'notes',''),
                    nullif(p->>'source_url',''),
                    coalesce(p->'metadata','{}'::jsonb) ||
                        case
                            when coalesce(p->>'relationship_id','') like 'PKG_%'
                            then jsonb_build_object('source_package_relationship_id',p->>'relationship_id')
                            else '{}'::jsonb
                        end
                )
                on conflict (relationship_id) do update set
                    source_type=excluded.source_type,
                    source_id=excluded.source_id,
                    relationship_type=excluded.relationship_type,
                    target_type=excluded.target_type,
                    target_id=excluded.target_id,
                    ownership_percent=excluded.ownership_percent,
                    operating_control=excluded.operating_control,
                    valid_from=excluded.valid_from,
                    valid_to=excluded.valid_to,
                    confidence=excluded.confidence,
                    record_status=excluded.record_status,
                    evidence_source_id=excluded.evidence_source_id,
                    notes=excluded.notes,
                    source_url=excluded.source_url,
                    metadata=coalesce(pc_relationships.metadata,'{}'::jsonb) || excluded.metadata;

                update pc_staged_records set
                    review_status='applied',
                    validation_status='reviewed',
                    resolution_status='READY',
                    resolution_method='sql_v20_relationship_apply',
                    resolution_confidence=1.0,
                    candidate_count=1,
                    resolved_entity_id=v_rel_id,
                    resolution_details=jsonb_build_object(
                        'canonical_source_id',v_source,
                        'canonical_target_id',v_target,
                        'canonical_relationship_id',v_rel_id
                    )
                 where staged_record_id=r.staged_record_id;

                v_applied:=v_applied+1;
                v_relationships:=v_relationships+1;
                continue;
            end if;

            -- ---------------------------------------------------------------
            -- EVENT LINKS / EVENT<->TRANSACTION BRIDGE
            -- ---------------------------------------------------------------
            if r.target_table='pc_event_links' then
                v_event := pc_resolve_package_object_id_v1(
                    p_ingestion_job_id,'event',p->>'event_id'
                );
                if v_event is null then
                    raise exception 'event_id % does not resolve canonically', p->>'event_id';
                end if;

                if lower(coalesce(p->>'linked_type','')) in ('transaction','deal') then
                    v_linked := pc_resolve_package_object_id_v1(
                        p_ingestion_job_id,'transaction',p->>'linked_id'
                    );
                    if v_linked is null then
                        raise exception 'transaction % does not resolve canonically', p->>'linked_id';
                    end if;

                    select coalesce(metadata,'{}'::jsonb)
                      into v_event_meta
                      from pc_events where event_id=v_event;

                    select coalesce(metadata,'{}'::jsonb)
                      into v_tx_meta
                      from pc_transactions where transaction_id=v_linked;

                    update pc_events
                       set metadata =
                           coalesce(v_event_meta,'{}'::jsonb)
                           || jsonb_build_object(
                                'linked_transaction_ids',
                                (
                                    select jsonb_agg(distinct x)
                                    from jsonb_array_elements_text(
                                        coalesce(v_event_meta->'linked_transaction_ids','[]'::jsonb)
                                        || jsonb_build_array(v_linked)
                                    ) x
                                ),
                                'transaction_link_method','canonical_metadata_bridge'
                              )
                     where event_id=v_event;

                    update pc_transactions
                       set metadata =
                           coalesce(v_tx_meta,'{}'::jsonb)
                           || jsonb_build_object(
                                'linked_event_ids',
                                (
                                    select jsonb_agg(distinct x)
                                    from jsonb_array_elements_text(
                                        coalesce(v_tx_meta->'linked_event_ids','[]'::jsonb)
                                        || jsonb_build_array(v_event)
                                    ) x
                                ),
                                'event_link_method','canonical_metadata_bridge'
                              )
                     where transaction_id=v_linked;

                    update pc_staged_records set
                        review_status='applied',
                        validation_status='reviewed',
                        resolution_status='READY',
                        resolution_method='sql_v20_event_transaction_bridge',
                        resolution_confidence=1.0,
                        candidate_count=1,
                        resolved_entity_id=v_linked,
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

                select event_link_id into v_existing
                  from pc_event_links
                 where event_id=v_event
                   and linked_type=p->>'linked_type'
                   and linked_id=v_linked
                   and relationship=p->>'relationship'
                 limit 1;

                v_event_link_id:=coalesce(
                    v_existing,
                    nullif(p->>'event_link_id',''),
                    'EVL_' || upper(substr(md5(
                        v_event || '|' || coalesce(p->>'linked_type','') || '|' ||
                        v_linked || '|' || coalesce(p->>'relationship','')
                    ),1,24))
                );

                insert into pc_event_links(
                    event_link_id,event_id,linked_type,linked_id,linked_name,
                    relationship,confidence,source_id,metadata
                )
                values(
                    v_event_link_id,
                    v_event,
                    p->>'linked_type',
                    v_linked,
                    nullif(p->>'linked_name',''),
                    p->>'relationship',
                    nullif(p->>'confidence',''),
                    nullif(p->>'source_id',''),
                    coalesce(p->'metadata','{}'::jsonb)
                )
                on conflict (event_link_id) do update set
                    event_id=excluded.event_id,
                    linked_type=excluded.linked_type,
                    linked_id=excluded.linked_id,
                    linked_name=excluded.linked_name,
                    relationship=excluded.relationship,
                    confidence=excluded.confidence,
                    source_id=excluded.source_id,
                    metadata=coalesce(pc_event_links.metadata,'{}'::jsonb) || excluded.metadata;

                update pc_staged_records set
                    review_status='applied',
                    validation_status='reviewed',
                    resolution_status='READY',
                    resolution_method='sql_v20_event_link_apply',
                    resolution_confidence=1.0,
                    candidate_count=1,
                    resolved_entity_id=v_event_link_id,
                    resolution_details=jsonb_build_object(
                        'canonical_event_id',v_event,
                        'canonical_linked_id',v_linked,
                        'canonical_event_link_id',v_event_link_id
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
                resolution_method='sql_v20_deferred_apply_error',
                resolution_details=jsonb_build_object(
                    'reason',sqlerrm,
                    'sqlstate',sqlstate,
                    'target_table',r.target_table
                )
             where staged_record_id=r.staged_record_id;

            v_review:=v_review+1;
        end;
    end loop;

    return jsonb_build_object(
        'applied',v_applied,
        'review',v_review,
        'participants_applied',v_participants,
        'relationships_applied',v_relationships,
        'event_links_applied',v_event_links,
        'transaction_bridges_applied',v_bridges
    );
end;
$$;

revoke all on function pc_resolve_package_object_id_v1(uuid,text,text) from public;
revoke all on function pc_apply_deferred_canonical_job_v1(uuid) from public;

grant execute on function pc_resolve_package_object_id_v1(uuid,text,text) to authenticated, service_role;
grant execute on function pc_apply_deferred_canonical_job_v1(uuid) to authenticated, service_role;

commit;

-- Verification
select role, display_name, role_group, active
from pc_meta_transaction_participant_roles
where role in ('buyer','seller','target','offeror','shareholder','sponsor','advisor','financier')
order by role;
