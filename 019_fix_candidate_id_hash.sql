-- Power & Corridors Trade System
-- 019_fix_candidate_id_hash.sql
-- Fixes candidate ID generation so it does not depend on pgcrypto.digest().
-- Staging only; no canonical business tables are written.

begin;

create or replace function pc_repair_unresolved_identity_candidates(
    p_ingestion_job_id uuid default null
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    r record;
    e pc_meta_entity_types%rowtype;
    v_payload jsonb;
    v_name text;
    v_norm text;
    v_candidate text;
    v_count integer;
    v_sql text;
    v_id text;
    v_prefix text;
    v_seed text;
    v_total integer := 0;
    v_matched integer := 0;
    v_new integer := 0;
    v_ambiguous integer := 0;
    v_invalid integer := 0;
begin
    for r in
        select *
        from pc_staged_records
        where (p_ingestion_job_id is null or ingestion_job_id = p_ingestion_job_id)
          and coalesce(review_status,'pending') not in ('rejected','applied')
          and target_table not in ('pc_relationships','pc_event_links','research_bundle')
          and coalesce(resolution_status,'UNRESOLVED') in
              ('UNRESOLVED','INVALID','NEW','MATCHED','AMBIGUOUS')
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
                   resolution_method='NO_ENTITY_METADATA',
                   resolution_details=coalesce(resolution_details,'{}'::jsonb)
                       || jsonb_build_object('repair_sql','019','reason','NO_ENTITY_METADATA')
             where staged_record_id=r.staged_record_id;
            v_invalid := v_invalid + 1;
            continue;
        end if;

        v_payload := coalesce(r.payload,'{}'::jsonb);

        update pc_staged_records
           set target_entity_type=e.entity_type,
               source_record_key=coalesce(nullif(source_record_key,''),natural_key,staged_record_id::text),
               review_status=coalesce(review_status,'pending')
         where staged_record_id=r.staged_record_id;

        -- Existing canonical ID supplied?
        v_id := nullif(trim(v_payload ->> e.primary_key_column),'');
        if v_id is not null then
            v_sql := format(
                'select count(*), min(%I::text) from %I where %I::text = $1',
                e.primary_key_column,e.table_name,e.primary_key_column
            );
            execute v_sql into v_count,v_candidate using v_id;

            if v_count = 1 then
                update pc_staged_records
                   set resolution_status='MATCHED',
                       resolved_entity_id=v_candidate,
                       resolution_method='PRIMARY_KEY_EXACT',
                       resolution_confidence=1.0,
                       candidate_count=1,
                       resolution_details=coalesce(resolution_details,'{}'::jsonb)
                           || jsonb_build_object('repair_sql','019','candidate_kind','MATCHED')
                 where staged_record_id=r.staged_record_id;
                perform pc_expand_staged_payload(r.staged_record_id);
                v_matched := v_matched + 1;
                continue;
            end if;
        end if;

        -- Canonical normalized name check.
        v_name := case
            when e.display_name_column is not null
            then nullif(trim(v_payload ->> e.display_name_column),'')
            else null
        end;

        if v_name is not null then
            v_norm := pc_normalize_name(v_name);
            v_sql := format(
                'select count(*), min(%I::text) from %I where pc_normalize_name(%I::text) = $1',
                e.primary_key_column,e.table_name,e.display_name_column
            );
            execute v_sql into v_count,v_candidate using v_norm;
        else
            v_count := 0;
            v_candidate := null;
        end if;

        if v_count = 1 then
            v_payload := jsonb_set(v_payload,array[e.primary_key_column],to_jsonb(v_candidate),true);
            update pc_staged_records
               set payload=v_payload,
                   resolution_status='MATCHED',
                   resolved_entity_id=v_candidate,
                   resolution_method='DISPLAY_NAME_NORMALIZED_EXACT',
                   resolution_confidence=1.0,
                   candidate_count=1,
                   validation_status=case when validation_status='invalid' then 'pending' else validation_status end,
                   resolution_details=coalesce(resolution_details,'{}'::jsonb)
                       || jsonb_build_object('repair_sql','019','candidate_kind','MATCHED')
             where staged_record_id=r.staged_record_id;
            perform pc_expand_staged_payload(r.staged_record_id);
            v_matched := v_matched + 1;

        elsif v_count > 1 then
            update pc_staged_records
               set resolution_status='AMBIGUOUS',
                   resolved_entity_id=null,
                   resolution_method='DISPLAY_NAME_NORMALIZED_EXACT',
                   resolution_confidence=0,
                   candidate_count=v_count,
                   resolution_details=coalesce(resolution_details,'{}'::jsonb)
                       || jsonb_build_object('repair_sql','019','candidate_kind','AMBIGUOUS')
             where staged_record_id=r.staged_record_id;
            v_ambiguous := v_ambiguous + 1;

        else
            -- No canonical match: classify as NEW and assign deterministic staging ID.
            v_prefix := coalesce(nullif(e.id_prefix,''),upper(e.entity_type));
            v_seed := coalesce(nullif(r.natural_key,''),nullif(r.source_record_key,''),r.staged_record_id::text);

            v_id := nullif(trim(v_payload ->> e.primary_key_column),'');
            if v_id is null then
                v_id := v_prefix || '_' || upper(substr(md5(v_seed),1,16));
            end if;

            v_payload := jsonb_set(v_payload,array[e.primary_key_column],to_jsonb(v_id),true);

            update pc_staged_records
               set payload=v_payload,
                   resolution_status='NEW',
                   resolved_entity_id=null,
                   resolution_method='NO_CANONICAL_MATCH',
                   resolution_confidence=1.0,
                   candidate_count=0,
                   validation_status=case when validation_status='invalid' then 'pending' else validation_status end,
                   resolution_details=coalesce(resolution_details,'{}'::jsonb)
                       || jsonb_build_object(
                            'repair_sql','019',
                            'candidate_kind','NEW',
                            'candidate_id',v_id
                          )
             where staged_record_id=r.staged_record_id;

            perform pc_expand_staged_payload(r.staged_record_id);
            v_new := v_new + 1;
        end if;
    end loop;

    if p_ingestion_job_id is not null then
        update pc_ingestion_jobs
           set stats=coalesce(stats,'{}'::jsonb) || jsonb_build_object(
               'repair019_total',v_total,
               'repair019_matched',v_matched,
               'repair019_new',v_new,
               'repair019_ambiguous',v_ambiguous,
               'repair019_invalid',v_invalid
           )
         where ingestion_job_id=p_ingestion_job_id;
    end if;

    return jsonb_build_object(
        'total',v_total,
        'matched',v_matched,
        'new',v_new,
        'ambiguous',v_ambiguous,
        'invalid',v_invalid
    );
end;
$$;

comment on function pc_repair_unresolved_identity_candidates(uuid) is
'SQL 019: repairs unresolved staged identities and generates deterministic candidate IDs without pgcrypto.digest dependency.';

commit;

-- Optional test for the Gulftainer job:
-- select pc_repair_unresolved_identity_candidates('7ea2f1bb-60c0-4c9d-96e7-1c56a879e227'::uuid);
