-- Power & Corridors Trade System
-- 015_prepare_entity_staging_jobs.sql
-- Server-side preparation and resolution of staged entity records.
-- Fixes older AI-research jobs that have target_table populated but target_entity_type null.

begin;

create or replace function pc_prepare_and_resolve_entity_job(p_ingestion_job_id uuid)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  r record;
  v_result record;
  v_prepared integer := 0;
  v_total integer := 0;
  v_matched integer := 0;
  v_new integer := 0;
  v_ambiguous integer := 0;
  v_invalid integer := 0;
begin
  -- Backfill logical entity type directly from the executable model registry.
  update pc_staged_records s
     set target_entity_type = m.entity_type,
         source_record_key = coalesce(nullif(s.source_record_key,''), nullif(s.natural_key,''), s.staged_record_id::text)
    from pc_meta_entity_types m
   where s.ingestion_job_id = p_ingestion_job_id
     and s.target_table = m.table_name
     and m.active
     and (s.target_entity_type is null or btrim(s.target_entity_type) = ''
          or s.source_record_key is null or btrim(s.source_record_key) = '');
  get diagnostics v_prepared = row_count;

  -- Relationship proposals are deliberately handled by SQL 011/013/014, not entity resolution.
  for r in
    select s.staged_record_id
      from pc_staged_records s
      join pc_meta_entity_types m
        on m.table_name = s.target_table and m.active
     where s.ingestion_job_id = p_ingestion_job_id
       and s.review_status not in ('rejected','applied')
       and s.target_table not in ('pc_relationships','pc_event_links')
     order by s.created_at, s.staged_record_id
  loop
    v_total := v_total + 1;
    select * into v_result from pc_resolve_staged_record(r.staged_record_id);
    case v_result.resolution_status
      when 'MATCHED' then v_matched := v_matched + 1;
      when 'NEW' then v_new := v_new + 1;
      when 'AMBIGUOUS' then v_ambiguous := v_ambiguous + 1;
      else v_invalid := v_invalid + 1;
    end case;
  end loop;

  update pc_ingestion_jobs
     set stats = coalesce(stats,'{}'::jsonb) || jsonb_build_object(
       'entity_prepared',v_prepared,
       'entity_resolved_total',v_total,
       'entity_matched',v_matched,
       'entity_new',v_new,
       'entity_ambiguous',v_ambiguous,
       'entity_invalid',v_invalid,
       'entity_resolved_at',now()
     )
   where ingestion_job_id = p_ingestion_job_id;

  return jsonb_build_object(
    'prepared',v_prepared,
    'total',v_total,
    'matched',v_matched,
    'new',v_new,
    'ambiguous',v_ambiguous,
    'invalid',v_invalid
  );
end;
$$;

comment on function pc_prepare_and_resolve_entity_job(uuid) is
  'Backfills target_entity_type/source_record_key from pc_meta_entity_types and resolves only canonical entity records in one ingestion job; relationship proposals are excluded.';

commit;
