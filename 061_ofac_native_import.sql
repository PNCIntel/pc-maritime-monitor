-- Native OFAC imports use the existing sanctions model and its typed JSON writer.
-- Requires 055_schema_safe_json_upsert.sql and 060_document_vessel_evidence.sql.
BEGIN;
CREATE TABLE IF NOT EXISTS public.pc_ofac_import_runs (
 import_id uuid PRIMARY KEY,
 document_id uuid NOT NULL REFERENCES public.pc_documents(document_id),
 file_sha256 text NOT NULL UNIQUE,
 data_as_of timestamptz NOT NULL,
 expected_counts jsonb NOT NULL,
 verified_counts jsonb NOT NULL DEFAULT '{}',
 status text NOT NULL DEFAULT 'importing',
 metadata jsonb NOT NULL DEFAULT '{}',
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.pc_ofac_import_batches (
 import_id uuid NOT NULL REFERENCES public.pc_ofac_import_runs(import_id),
 batch_number integer NOT NULL,
 batch_sha256 text NOT NULL,
 row_counts jsonb NOT NULL,
 PRIMARY KEY(import_id,batch_number)
);
CREATE TABLE IF NOT EXISTS public.pc_ofac_designation_programmes (
 import_id uuid NOT NULL REFERENCES public.pc_ofac_import_runs(import_id),
 designation_id text NOT NULL,
 programme_id text NOT NULL,
 programme_code text NOT NULL,
 PRIMARY KEY(import_id,designation_id,programme_code)
);
CREATE TABLE IF NOT EXISTS public.pc_ofac_source_relationships (
 import_id uuid NOT NULL REFERENCES public.pc_ofac_import_runs(import_id),
 source_relationship_id text NOT NULL,
 source_external_id text NOT NULL,
 target_external_id text NOT NULL,
 relationship_type text NOT NULL,
 target_name text,
 endpoint_status text NOT NULL,
 raw_record jsonb NOT NULL,
 PRIMARY KEY(import_id,source_external_id,source_relationship_id)
);
CREATE OR REPLACE FUNCTION public.pc_ofac_import_schema()
RETURNS jsonb LANGUAGE sql STABLE SECURITY DEFINER SET search_path=public,pg_temp AS $$
 SELECT coalesce(jsonb_object_agg(t.table_name,t.columns),'{}'::jsonb)
 FROM (SELECT c.table_name,jsonb_agg(jsonb_build_object('column',c.column_name,'type',c.data_type,
   'nullable',c.is_nullable,'default',c.column_default) ORDER BY c.ordinal_position) AS columns
  FROM information_schema.columns c WHERE c.table_schema='public' AND c.table_name IN
  ('pc_source_records','pc_sources','pc_source_feeds','pc_source_snapshots','pc_sanctions_authorities',
   'pc_sanctions_programmes','pc_sanctions_designations','pc_sanctions_aliases',
   'pc_sanctions_addresses','pc_sanctions_identifiers','pc_sanctions_measures','pc_sanctions_links')
  GROUP BY c.table_name) t;
$$;
CREATE OR REPLACE FUNCTION public.pc_apply_ofac_import_batch(
 p_import_id uuid,p_batch_number integer,p_batch_sha256 text,p_operations jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE op jsonb; payload jsonb; tab text; pk text; counts jsonb:='{}'; old_hash text; n integer;
BEGIN
 PERFORM 1 FROM public.pc_ofac_import_runs WHERE import_id=p_import_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Import run not found'; END IF;
 SELECT batch_sha256 INTO old_hash FROM public.pc_ofac_import_batches
 WHERE import_id=p_import_id AND batch_number=p_batch_number;
 IF old_hash IS NOT NULL THEN
  IF old_hash<>p_batch_sha256 THEN RAISE EXCEPTION 'Retry batch content changed'; END IF;
  RETURN jsonb_build_object('reused',true,'batch_number',p_batch_number);
 END IF;
 IF jsonb_typeof(p_operations) IS DISTINCT FROM 'array' THEN RAISE EXCEPTION 'Operation array required'; END IF;
 FOR op IN SELECT value FROM jsonb_array_elements(p_operations) LOOP
  tab:=op->>'table'; pk:=op->>'primary_key'; payload:=op->'payload';
  IF tab NOT IN ('pc_source_records','pc_sources','pc_source_feeds','pc_source_snapshots','pc_sanctions_authorities',
   'pc_sanctions_programmes','pc_sanctions_designations','pc_sanctions_aliases','pc_sanctions_addresses',
   'pc_sanctions_identifiers','pc_sanctions_measures','pc_sanctions_links','pc_mobile_assets',
   'pc_entities','pc_relationships','pc_vessel_identity_history','pc_document_links') THEN
   RAISE EXCEPTION 'Unsupported OFAC target %',tab;
  END IF;
  IF pk IS NULL OR NOT EXISTS(SELECT 1 FROM pg_index i JOIN pg_attribute a ON a.attrelid=i.indrelid
    AND a.attnum=ANY(i.indkey) WHERE i.indrelid=to_regclass('public.'||tab) AND i.indisprimary AND a.attname=pk) THEN
   RAISE EXCEPTION 'Invalid primary key for %',tab;
  END IF;
  PERFORM public.pc_upsert_json(tab,payload,ARRAY[pk]);
  n:=coalesce((counts->>tab)::integer,0)+1;
  counts:=jsonb_set(counts,ARRAY[tab],to_jsonb(n));
 END LOOP;
 INSERT INTO public.pc_ofac_import_batches(import_id,batch_number,batch_sha256,row_counts)
 VALUES(p_import_id,p_batch_number,p_batch_sha256,counts);
 RETURN jsonb_build_object('reused',false,'batch_number',p_batch_number,'row_counts',counts);
END $$;
CREATE OR REPLACE FUNCTION public.pc_verify_ofac_import(p_import_id uuid,p_snapshot_id text)
RETURNS jsonb LANGUAGE sql STABLE SECURITY DEFINER SET search_path=public,pg_temp AS $$
 SELECT jsonb_build_object(
  'source_records',(SELECT count(*) FROM public.pc_source_records WHERE source_snapshot_id::text=p_snapshot_id),
  'features',(SELECT coalesce(sum(jsonb_array_length(coalesce(metadata->'features','[]'::jsonb))),0)
    FROM public.pc_sanctions_designations WHERE source_snapshot_id::text=p_snapshot_id),
  'legal_authorities',(SELECT coalesce(sum(jsonb_array_length(coalesce(metadata->'legal_authorities','[]'::jsonb))),0)
    FROM public.pc_sanctions_designations WHERE source_snapshot_id::text=p_snapshot_id),
  'sanctions_types',(SELECT coalesce(sum(jsonb_array_length(coalesce(metadata->'sanctions_types','[]'::jsonb))),0)
    FROM public.pc_sanctions_designations WHERE source_snapshot_id::text=p_snapshot_id),
  'programmes',(SELECT count(*) FROM public.pc_ofac_designation_programmes WHERE import_id=p_import_id));
$$;
REVOKE ALL ON FUNCTION public.pc_verify_ofac_import(uuid,text) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.pc_verify_ofac_import(uuid,text) TO service_role,postgres;
-- Evidence joins retain the distinct OFAC and UAE authorities on the SAME hull.
CREATE OR REPLACE VIEW public.pc_v_uae_ofac_vessel_overlap AS
SELECT o.document_id AS uae_document_id,o.mobile_asset_id,m.name,m.imo,
 o.raw_record->>'flag' AS uae_listed_flag,a.circular_reference,a.scope_text,
 s.sanctions_designation_id,s.primary_name AS ofac_name,s.designation_date,s.status AS ofac_status,
 s.metadata->'all_programme_codes' AS ofac_programmes,s.source_snapshot_id,
 auth.authority_code,auth.authority_name
FROM public.pc_document_vessel_observations o
JOIN public.pc_document_access_measures a USING(document_id)
JOIN public.pc_mobile_assets m USING(mobile_asset_id)
JOIN public.pc_sanctions_links l ON l.linked_id=m.mobile_asset_id AND l.linked_type='mobile_asset'
JOIN public.pc_sanctions_designations s USING(sanctions_designation_id)
JOIN public.pc_sanctions_authorities auth USING(sanctions_authority_id)
WHERE auth.authority_code='OFAC';
ALTER TABLE public.pc_ofac_import_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pc_ofac_import_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pc_ofac_designation_programmes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pc_ofac_source_relationships ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.pc_ofac_import_runs,public.pc_ofac_import_batches,public.pc_ofac_designation_programmes,
 public.pc_ofac_source_relationships,public.pc_v_uae_ofac_vessel_overlap FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON public.pc_ofac_import_runs,public.pc_ofac_designation_programmes,
 public.pc_ofac_source_relationships TO service_role,postgres;
GRANT SELECT ON public.pc_ofac_import_batches,public.pc_v_uae_ofac_vessel_overlap TO service_role,postgres;
REVOKE ALL ON FUNCTION public.pc_ofac_import_schema(),public.pc_apply_ofac_import_batch(uuid,integer,text,jsonb)
 FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.pc_ofac_import_schema(),public.pc_apply_ofac_import_batch(uuid,integer,text,jsonb)
 TO service_role,postgres;
NOTIFY pgrst,'reload schema';
COMMIT;
