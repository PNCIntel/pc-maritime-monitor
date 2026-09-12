-- Power & Corridors Trade System
-- 016_prepare_canonical_candidates.sql
-- Server-side preparation of staged canonical entity candidates.
-- Resolves identity first, reuses MATCHED canonical IDs, and assigns deterministic
-- P&C IDs to genuinely NEW records. Staging only: does not write canonical business tables.

begin;

create extension if not exists pgcrypto;

create or replace function pc_prepare_canonical_candidates(p_ingestion_job_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  r record;
  e pc_meta_entity_types%rowtype;
  v_result record;
  v_id text;
  v_prefix text;
  v_seed text;
  v_payload jsonb;
  v_total integer := 0;
  v_prepared integer := 0;
  v_matched integer := 0;
  v_new integer := 0;
  v_ambiguous integer := 0;
  v_invalid integer := 0;
begin
  for r in
    select *
    from pc_staged_records
    where ingestion_job_id = p_ingestion_job_id
      and target_table not in ('pc_relationships','pc_event_links')
      and review_status not in ('rejected','applied')
    order by created_at, staged_record_id
  loop
    v_total := v_total + 1;

    select * into e
    from pc_meta_entity_types
    where active
      and (table_name = r.target_table or entity_type = r.target_entity_type)
    order by case when table_name = r.target_table then 0 else 1 end
    limit 1;

    if not found then
      update pc_staged_records
         set resolution_status='INVALID',
             resolution_method='NO_ENTITY_METADATA'
       where staged_record_id=r.staged_record_id;
      v_invalid := v_invalid + 1;
      continue;
    end if;

    update pc_staged_records
       set target_entity_type=e.entity_type,
           source_record_key=coalesce(nullif(source_record_key,''),natural_key,staged_record_id::text)
     where staged_record_id=r.staged_record_id;

    select * into v_result from pc_resolve_staged_record(r.staged_record_id);

    v_payload := coalesce(r.payload,'{}'::jsonb);

    if v_result.resolution_status = 'MATCHED' then
      v_id := v_result.resolved_entity_id;
      v_matched := v_matched + 1;
    elsif v_result.resolution_status = 'NEW' then
      v_prefix := coalesce(nullif(e.id_prefix,''), upper(e.entity_type));
      v_seed := coalesce(nullif(r.natural_key,''), nullif(r.source_record_key,''), r.staged_record_id::text);
      v_id := v_payload ->> e.primary_key_column;
      if coalesce(trim(v_id),'') = '' then
        v_id := v_prefix || '_' || upper(substr(encode(digest(v_seed,'sha256'),'hex'),1,16));
      end if;
      v_new := v_new + 1;
    elsif v_result.resolution_status = 'AMBIGUOUS' then
      v_ambiguous := v_ambiguous + 1;
      continue;
    else
      v_invalid := v_invalid + 1;
      continue;
    end if;

    -- Place the canonical/reused ID into the staged proposal. This is still staging only.
    v_payload := jsonb_set(v_payload, array[e.primary_key_column], to_jsonb(v_id), true);

    update pc_staged_records
       set payload=v_payload,
           resolved_entity_id=case when v_result.resolution_status='MATCHED' then v_id else resolved_entity_id end,
           validation_status=case when validation_status='invalid' then 'pending' else validation_status end
     where staged_record_id=r.staged_record_id;

    -- Refresh expanded EAV values so metadata views see the prepared primary key.
    perform pc_expand_staged_payload(r.staged_record_id);
    v_prepared := v_prepared + 1;
  end loop;

  update pc_ingestion_jobs
     set stats = coalesce(stats,'{}'::jsonb) || jsonb_build_object(
       'candidate_prepare_total',v_total,
       'candidate_prepared',v_prepared,
       'candidate_matched',v_matched,
       'candidate_new',v_new,
       'candidate_ambiguous',v_ambiguous,
       'candidate_invalid',v_invalid
     )
   where ingestion_job_id=p_ingestion_job_id;

  return jsonb_build_object(
    'total',v_total,
    'prepared',v_prepared,
    'matched',v_matched,
    'new',v_new,
    'ambiguous',v_ambiguous,
    'invalid',v_invalid
  );
end;
$$;

comment on function pc_prepare_canonical_candidates(uuid) is
  'Prepares staged canonical entity candidates: resolves identities, reuses MATCHED IDs, assigns deterministic IDs to NEW rows, and updates staging only.';

commit;
