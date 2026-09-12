-- P&C Trade System
-- SQL 014: Recover missing generic relationship endpoints from staged AI proposals
-- Run after SQL 013. Safe to re-run. Does not apply canonical relationships.

begin;

create or replace function pc_stage_generic_relationship(p_staged_record_id uuid)
returns uuid
language plpgsql
as $$
declare
  s pc_staged_records%rowtype;
  p jsonb;
  m jsonb;
  src_obj jsonb;
  tgt_obj jsonb;
  v_rel_id uuid;
  v_from_type text;
  v_to_type text;
  v_from_name text;
  v_to_name text;
  v_from_key text;
  v_to_key text;
  v_from_identifier_type text;
  v_from_identifier_value text;
  v_to_identifier_type text;
  v_to_identifier_value text;
  v_relationship text;
  v_source_provenance text;
  v_rel_slug text;
  v_natural text;
  v_pos integer;
  v_derived boolean := false;
begin
  select * into s from pc_staged_records where staged_record_id=p_staged_record_id;
  if not found then raise exception 'Unknown staged record %',p_staged_record_id; end if;
  if s.target_table <> 'pc_relationships' then
    raise exception 'Staged record % targets %, not pc_relationships',p_staged_record_id,s.target_table;
  end if;

  p := coalesce(s.payload,'{}'::jsonb);
  m := case when jsonb_typeof(p->'metadata')='object' then p->'metadata' else '{}'::jsonb end;
  src_obj := case when jsonb_typeof(p->'source')='object' then p->'source' else '{}'::jsonb end;
  tgt_obj := case when jsonb_typeof(p->'target')='object' then p->'target' else '{}'::jsonb end;

  v_from_type := pc_relationship_endpoint_type(coalesce(
    nullif(p->>'source_type',''),nullif(p->>'from_type',''),
    nullif(src_obj->>'type',''),nullif(src_obj->>'entity_type',''),
    nullif(m->>'source_type',''),nullif(m->>'from_type','')
  ));
  v_to_type := pc_relationship_endpoint_type(coalesce(
    nullif(p->>'target_type',''),nullif(p->>'to_type',''),
    nullif(tgt_obj->>'type',''),nullif(tgt_obj->>'entity_type',''),
    nullif(m->>'target_type',''),nullif(m->>'to_type','')
  ));
  v_relationship := coalesce(
    nullif(p->>'relationship_type',''),nullif(p->>'relationship',''),
    nullif(m->>'relationship_type',''),'related_to'
  );

  v_from_key := coalesce(
    nullif(p->>'source_id',''),nullif(p->>'from_id',''),nullif(p->>'from_source_key',''),
    nullif(src_obj->>'id',''),nullif(src_obj->>'entity_id',''),nullif(m->>'source_id','')
  );
  v_to_key := coalesce(
    nullif(p->>'target_id',''),nullif(p->>'to_id',''),nullif(p->>'to_source_key',''),
    nullif(tgt_obj->>'id',''),nullif(tgt_obj->>'entity_id',''),nullif(m->>'target_id','')
  );

  v_from_name := coalesce(
    nullif(p->>'source_name',''),nullif(p->>'from_name',''),nullif(p->>'source_label',''),
    nullif(p->>'source_entity_name',''),nullif(src_obj->>'name',''),nullif(src_obj->>'label',''),
    nullif(m->>'source_name',''),nullif(m->>'from_name','')
  );
  v_to_name := coalesce(
    nullif(p->>'target_name',''),nullif(p->>'to_name',''),nullif(p->>'target_label',''),
    nullif(p->>'target_entity_name',''),nullif(p->>'target_asset_name',''),
    nullif(tgt_obj->>'name',''),nullif(tgt_obj->>'label',''),
    nullif(m->>'target_name',''),nullif(m->>'to_name','')
  );

  v_from_identifier_type := coalesce(nullif(p->>'source_identifier_type',''),nullif(p->>'from_identifier_type',''),nullif(src_obj->>'identifier_type',''),nullif(m->>'source_identifier_type',''));
  v_from_identifier_value := coalesce(nullif(p->>'source_identifier_value',''),nullif(p->>'from_identifier_value',''),nullif(src_obj->>'identifier_value',''),nullif(m->>'source_identifier_value',''));
  v_to_identifier_type := coalesce(nullif(p->>'target_identifier_type',''),nullif(p->>'to_identifier_type',''),nullif(tgt_obj->>'identifier_type',''),nullif(m->>'target_identifier_type',''));
  v_to_identifier_value := coalesce(nullif(p->>'target_identifier_value',''),nullif(p->>'to_identifier_value',''),nullif(tgt_obj->>'identifier_value',''),nullif(m->>'target_identifier_value',''));

  if v_from_identifier_type is null and nullif(m->>'source_imo','') is not null then
    v_from_identifier_type := 'IMO'; v_from_identifier_value := m->>'source_imo';
  end if;
  if v_to_identifier_type is null and nullif(m->>'target_imo','') is not null then
    v_to_identifier_type := 'IMO'; v_to_identifier_value := m->>'target_imo';
  end if;

  -- Compatibility recovery for older AI relationship proposals that provided only
  -- a stable natural_key such as gulftainer_operates_jubail_industrial_port.
  -- This is used only to recover staged endpoint labels; canonical resolution and
  -- analyst review are still required before any relationship can be applied.
  v_natural := lower(coalesce(s.natural_key,s.source_record_key,''));
  v_rel_slug := regexp_replace(lower(v_relationship),'[^a-z0-9]+','_','g');
  v_rel_slug := trim(both '_' from v_rel_slug);
  if v_natural <> '' and v_rel_slug <> '' then
    v_pos := strpos(v_natural, '_'||v_rel_slug||'_');
    if v_pos > 0 then
      if v_from_name is null then
        v_from_name := initcap(replace(left(v_natural,v_pos-1),'_',' '));
        v_derived := true;
      end if;
      if v_to_name is null then
        v_to_name := initcap(replace(substr(v_natural,v_pos+length(v_rel_slug)+2),'_',' '));
        v_derived := true;
      end if;
    end if;
  end if;

  v_source_provenance := coalesce(s.source_id,nullif(p->>'evidence_source_id',''),nullif(p->>'source_record_id',''));
  v_from_type := coalesce(v_from_type,'entity');
  v_to_type := coalesce(v_to_type,'asset');

  select staged_relationship_id into v_rel_id
  from pc_staged_relationships
  where source_staged_record_id=p_staged_record_id
  order by created_at desc
  limit 1;

  if v_rel_id is null then
    insert into pc_staged_relationships(
      ingestion_job_id,source_staged_record_id,relationship_type,
      from_entity_type,from_source_key,from_identifier_type,from_identifier_value,from_name,
      to_entity_type,to_source_key,to_identifier_type,to_identifier_value,to_name,
      valid_from,valid_to,confidence,source_id,resolution_status,metadata
    ) values (
      s.ingestion_job_id,s.staged_record_id,v_relationship,
      v_from_type,v_from_key,v_from_identifier_type,v_from_identifier_value,v_from_name,
      v_to_type,v_to_key,v_to_identifier_type,v_to_identifier_value,v_to_name,
      nullif(p->>'valid_from','')::date,nullif(p->>'valid_to','')::date,coalesce(s.confidence,1.0),v_source_provenance,'UNRESOLVED',
      jsonb_build_object(
        'relationship_id',p->>'relationship_id',
        'original_source_type',p->>'source_type',
        'original_target_type',p->>'target_type',
        'endpoint_labels_derived_from_natural_key',v_derived,
        'original_payload',p
      )
    ) returning staged_relationship_id into v_rel_id;
  else
    update pc_staged_relationships set
      ingestion_job_id=s.ingestion_job_id,
      relationship_type=v_relationship,
      from_entity_type=v_from_type,
      from_source_key=v_from_key,
      from_identifier_type=v_from_identifier_type,
      from_identifier_value=v_from_identifier_value,
      from_name=v_from_name,
      to_entity_type=v_to_type,
      to_source_key=v_to_key,
      to_identifier_type=v_to_identifier_type,
      to_identifier_value=v_to_identifier_value,
      to_name=v_to_name,
      valid_from=nullif(p->>'valid_from','')::date,
      valid_to=nullif(p->>'valid_to','')::date,
      confidence=coalesce(s.confidence,confidence),
      source_id=coalesce(v_source_provenance,source_id),
      resolution_status='UNRESOLVED',
      apply_status='PENDING',
      apply_error=null,
      metadata=coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'relationship_id',p->>'relationship_id',
        'original_source_type',p->>'source_type',
        'original_target_type',p->>'target_type',
        'endpoint_labels_derived_from_natural_key',v_derived,
        'original_payload',p
      )
    where staged_relationship_id=v_rel_id;
  end if;

  return v_rel_id;
end;
$$;


-- Re-stage and re-resolve the existing generic relationship backlog with the repaired parser.
do $$
declare r record; rid uuid;
begin
  for r in
    select staged_record_id from pc_staged_records
    where target_table='pc_relationships'
      and coalesce(review_status,'pending') not in ('rejected','applied')
  loop
    begin
      rid := pc_stage_generic_relationship(r.staged_record_id);
      perform pc_resolve_generic_relationship(rid);
    exception when others then
      raise notice 'Relationship recovery failed for %: %',r.staged_record_id,sqlerrm;
    end;
  end loop;
end $$;

commit;
