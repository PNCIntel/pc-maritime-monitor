-- Power & Corridors Trade System
-- 020_corporate_entity_relationships.sql
-- First-class company-to-company / entity-to-entity corporate graph support.
-- Run AFTER SQL 013 (generic relationship resolution) and later repair migrations.
-- This migration is staging-safe: the staging RPC does not write canonical pc_relationships
-- until the existing SQL 013 READY/apply workflow is used.

begin;

-- ---------------------------------------------------------------------------
-- 1. Register corporate relationship families in the executable meta-model.
--    The metadata key is namespaced; metadata.canonical_relationship_type is
--    the value written to pc_relationships.relationship_type.
-- ---------------------------------------------------------------------------

insert into pc_meta_relationship_types(
    relationship_type,
    from_entity_type,
    to_entity_type,
    relationship_table,
    from_key_column,
    to_key_column,
    relationship_type_column,
    inverse_relationship_type,
    cardinality,
    active,
    description,
    metadata
)
values
    ('corporate_parent_of','entity','entity','pc_relationships',
     'source_id','target_id','relationship_type','subsidiary_of','1:N',true,
     'Parent company/entity relationship.',
     '{"canonical_relationship_type":"parent_of","relationship_family":"corporate"}'::jsonb),

    ('corporate_owns','entity','entity','pc_relationships',
     'source_id','target_id','relationship_type','owned_by','N:N',true,
     'Company/entity ownership relationship.',
     '{"canonical_relationship_type":"owns","relationship_family":"corporate"}'::jsonb),

    ('corporate_controls','entity','entity','pc_relationships',
     'source_id','target_id','relationship_type','controlled_by','N:N',true,
     'Company/entity control relationship.',
     '{"canonical_relationship_type":"controls","relationship_family":"corporate"}'::jsonb),

    ('corporate_affiliate_of','entity','entity','pc_relationships',
     'source_id','target_id','relationship_type','affiliate_of','N:N',true,
     'Corporate affiliate relationship.',
     '{"canonical_relationship_type":"affiliate_of","relationship_family":"corporate","symmetric":true}'::jsonb),

    ('corporate_joint_venture_with','entity','entity','pc_relationships',
     'source_id','target_id','relationship_type','joint_venture_with','N:N',true,
     'Joint venture relationship between entities.',
     '{"canonical_relationship_type":"joint_venture_with","relationship_family":"corporate","symmetric":true}'::jsonb),

    ('corporate_invested_in','entity','entity','pc_relationships',
     'source_id','target_id','relationship_type','investment_from','N:N',true,
     'Equity or strategic investment in another entity.',
     '{"canonical_relationship_type":"invested_in","relationship_family":"corporate"}'::jsonb),

    ('corporate_acquired','entity','entity','pc_relationships',
     'source_id','target_id','relationship_type','acquired_by','N:N',true,
     'Acquisition relationship.',
     '{"canonical_relationship_type":"acquired","relationship_family":"corporate"}'::jsonb)

on conflict (relationship_type) do update set
    from_entity_type=excluded.from_entity_type,
    to_entity_type=excluded.to_entity_type,
    relationship_table=excluded.relationship_table,
    from_key_column=excluded.from_key_column,
    to_key_column=excluded.to_key_column,
    relationship_type_column=excluded.relationship_type_column,
    inverse_relationship_type=excluded.inverse_relationship_type,
    cardinality=excluded.cardinality,
    active=true,
    description=excluded.description,
    metadata=excluded.metadata;


-- ---------------------------------------------------------------------------
-- 2. Controlled staging RPC for one company/entity -> company/entity edge.
--    It creates a normal pc_staged_records relationship proposal, then invokes
--    the existing SQL 013 staging + endpoint resolver. No canonical write occurs.
-- ---------------------------------------------------------------------------

create or replace function pc_stage_corporate_relationship(
    p_ingestion_job_id uuid,
    p_source_name text,
    p_target_name text,
    p_relationship_type text default 'parent_of',
    p_source_id text default null,
    p_target_id text default null,
    p_evidence_source_id text default null,
    p_confidence numeric default 1.0,
    p_ownership_percent numeric default null,
    p_operating_control boolean default null,
    p_notes text default null,
    p_metadata jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_staged_record_id uuid;
    v_staged_relationship_id uuid;
    v_payload jsonb;
    v_natural_key text;
    v_resolution jsonb;
    v_rel text;
begin
    if p_ingestion_job_id is null then
        raise exception 'p_ingestion_job_id is required';
    end if;
    if coalesce(trim(p_source_name),'')='' or coalesce(trim(p_target_name),'')='' then
        raise exception 'source_name and target_name are required';
    end if;

    v_rel := lower(trim(coalesce(p_relationship_type,'parent_of')));
    if v_rel not in (
        'parent_of','owns','controls','affiliate_of','joint_venture_with',
        'invested_in','acquired'
    ) then
        raise exception 'Unsupported corporate relationship_type: %',v_rel;
    end if;

    if pc_normalize_name(p_source_name)=pc_normalize_name(p_target_name) then
        raise exception 'Source and target cannot be the same corporate entity';
    end if;

    v_natural_key :=
        'corp_' ||
        regexp_replace(pc_normalize_name(p_source_name),'[^a-z0-9]+','_','g') ||
        '_' || v_rel || '_' ||
        regexp_replace(pc_normalize_name(p_target_name),'[^a-z0-9]+','_','g');

    v_payload := jsonb_strip_nulls(jsonb_build_object(
        'source_type','entity',
        'source_name',p_source_name,
        'source_id',p_source_id,
        'relationship_type',v_rel,
        'target_type','entity',
        'target_name',p_target_name,
        'target_id',p_target_id,
        'ownership_percent',p_ownership_percent,
        'operating_control',p_operating_control,
        'evidence_source_id',p_evidence_source_id,
        'notes',p_notes,
        'metadata',coalesce(p_metadata,'{}'::jsonb) || jsonb_build_object(
            'relationship_family','corporate',
            'staged_by','pc_stage_corporate_relationship'
        )
    ));

    -- Reuse an existing pending proposal in the same job when the natural key matches.
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
        ) values (
            p_ingestion_job_id,'pc_relationships',v_natural_key,v_natural_key,'REVIEW',v_payload,
            coalesce(p_confidence,1.0),'pending','pending','UNRESOLVED'
        )
        returning staged_record_id into v_staged_record_id;
    else
        update pc_staged_records
           set payload=v_payload,
               confidence=coalesce(p_confidence,confidence),
               validation_status='pending',
               review_status='pending',
               resolution_status='UNRESOLVED',
               resolution_method=null,
               resolved_entity_id=null,
               resolution_details=coalesce(resolution_details,'{}'::jsonb)
                    || jsonb_build_object('restaged_by','SQL020')
         where staged_record_id=v_staged_record_id;
    end if;

    v_staged_relationship_id := pc_stage_generic_relationship(v_staged_record_id);
    v_resolution := pc_resolve_generic_relationship(v_staged_relationship_id);

    return jsonb_build_object(
        'staged_record_id',v_staged_record_id,
        'staged_relationship_id',v_staged_relationship_id,
        'natural_key',v_natural_key,
        'relationship_type',v_rel,
        'resolution',v_resolution
    );
end;
$$;


-- ---------------------------------------------------------------------------
-- 3. Corporate graph views: canonical and staged.
-- ---------------------------------------------------------------------------

create or replace view pc_v_corporate_relationships as
select
    r.relationship_id,
    r.source_id,
    se.name as source_name,
    r.relationship_type,
    r.target_id,
    te.name as target_name,
    r.ownership_percent,
    r.operating_control,
    r.valid_from,
    r.valid_to,
    r.confidence,
    r.record_status,
    r.evidence_source_id,
    r.notes,
    r.metadata
from pc_relationships r
left join pc_entities se on se.entity_id=r.source_id
left join pc_entities te on te.entity_id=r.target_id
where lower(coalesce(r.source_type,''))='entity'
  and lower(coalesce(r.target_type,''))='entity';

create or replace view pc_v_staged_corporate_relationships as
select
    sr.staged_relationship_id,
    sr.ingestion_job_id,
    sr.source_staged_record_id,
    s.natural_key,
    sr.relationship_type,
    sr.from_name as source_name,
    sr.resolved_from_entity_id as source_id,
    sr.from_resolution_method as source_resolution_method,
    sr.to_name as target_name,
    sr.resolved_to_entity_id as target_id,
    sr.to_resolution_method as target_resolution_method,
    sr.resolution_status,
    sr.apply_status,
    sr.existing_relationship_id,
    sr.canonical_relationship_id,
    sr.confidence,
    sr.source_id as evidence_source_id,
    sr.created_at,
    sr.resolved_at,
    sr.applied_at
from pc_staged_relationships sr
left join pc_staged_records s on s.staged_record_id=sr.source_staged_record_id
where sr.from_entity_type='entity'
  and sr.to_entity_type='entity';


comment on function pc_stage_corporate_relationship(
    uuid,text,text,text,text,text,text,numeric,numeric,boolean,text,jsonb
) is
'Stages one source-backed company/entity to company/entity corporate edge and immediately invokes the generic SQL 013 resolver; canonical apply remains a separate controlled step.';

comment on view pc_v_corporate_relationships is
'Canonical company/entity-to-company/entity corporate graph with endpoint names.';

comment on view pc_v_staged_corporate_relationships is
'Staged/resolved company/entity corporate relationship proposals awaiting or recording canonical apply.';

commit;
