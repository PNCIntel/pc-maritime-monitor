-- Retain originals and ingest page-addressable vessel evidence into the shared graph.
-- Prerequisites: 028_document_ingestion.sql and 10_SUPABASE_V18_DOCUMENTS_PATCHED.sql.
BEGIN;
CREATE EXTENSION IF NOT EXISTS pgcrypto;
ALTER TABLE public.pc_documents ADD COLUMN IF NOT EXISTS file_name text;
ALTER TABLE public.pc_documents ADD COLUMN IF NOT EXISTS file_sha256 text;
ALTER TABLE public.pc_documents ADD COLUMN IF NOT EXISTS mime_type text;
ALTER TABLE public.pc_documents ADD COLUMN IF NOT EXISTS storage_path text;
ALTER TABLE public.pc_documents ADD COLUMN IF NOT EXISTS extracted_text text;
ALTER TABLE public.pc_documents ADD COLUMN IF NOT EXISTS extraction_status text DEFAULT 'pending';
CREATE UNIQUE INDEX IF NOT EXISTS uq_pc_documents_hash ON public.pc_documents(file_sha256) WHERE file_sha256 IS NOT NULL;
INSERT INTO storage.buckets(id,name,public) VALUES('pc-source-documents','pc-source-documents',false)
ON CONFLICT(id) DO UPDATE SET public=false;

CREATE TABLE IF NOT EXISTS public.pc_document_vessel_observations (
 document_id uuid NOT NULL REFERENCES public.pc_documents(document_id),
 row_key text NOT NULL,
 page_number integer NOT NULL CHECK(page_number>0),
 mobile_asset_id text REFERENCES public.pc_mobile_assets(mobile_asset_id),
 resolution_status text NOT NULL CHECK(resolution_status IN ('matched_imo','created_imo','held_invalid_imo','held_ambiguous_imo')),
 raw_record jsonb NOT NULL,
 observed_at date, -- stays null unless the source explicitly dates the observation
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(document_id,row_key)
);
CREATE INDEX IF NOT EXISTS pc_document_vessel_target_idx ON public.pc_document_vessel_observations(mobile_asset_id);
CREATE TABLE IF NOT EXISTS public.pc_document_vessel_research_queue (
 document_id uuid NOT NULL,
 row_key text NOT NULL,
 mobile_asset_id text REFERENCES public.pc_mobile_assets(mobile_asset_id),
 imo text NOT NULL,
 research_gaps jsonb NOT NULL,
 status text NOT NULL DEFAULT 'queued',
 research_payload jsonb,
 ingestion_job_id uuid,
 updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(document_id,row_key),
 FOREIGN KEY(document_id,row_key) REFERENCES public.pc_document_vessel_observations(document_id,row_key)
);
ALTER TABLE public.pc_document_vessel_research_queue ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.pc_document_vessel_research_queue FROM PUBLIC,anon,authenticated;
GRANT SELECT,UPDATE ON public.pc_document_vessel_research_queue TO service_role,postgres;

-- These are document-backed regulatory claims, not assumed OFAC/EU/UK designations.
CREATE TABLE IF NOT EXISTS public.pc_document_access_measures (
 document_id uuid PRIMARY KEY REFERENCES public.pc_documents(document_id),
 authority_name text, circular_reference text, jurisdiction text,
 issue_date date, effective_from date, effective_to date,
 restriction_type text NOT NULL DEFAULT 'port_access',
 scope_text text NOT NULL, legal_basis text, evidence_excerpt text NOT NULL,
 status text NOT NULL DEFAULT 'documented',
 metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE OR REPLACE FUNCTION public.pc_apply_document_vessel_evidence(
 p_document_id uuid,p_rows jsonb,p_instrument jsonb,p_coverage jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE
 d public.pc_documents%ROWTYPE; r jsonb; vessel_ids text[]; vid text; state text;
 rownum integer:=0; matched integer:=0; created integer:=0; held integer:=0;
 imo_value text; checksum integer; k integer; row_key_value text;
 owner_role text; owner_name text; entity_ids text[]; rid text;
BEGIN
 SELECT * INTO d FROM public.pc_documents WHERE document_id=p_document_id FOR UPDATE;
 IF NOT FOUND OR nullif(d.storage_path,'') IS NULL OR nullif(d.file_sha256,'') IS NULL THEN
  RAISE EXCEPTION 'Retained document required before vessel publication'; END IF;
 IF jsonb_typeof(p_rows) IS DISTINCT FROM 'array' OR jsonb_typeof(p_coverage->'pages') IS DISTINCT FROM 'array' OR p_coverage->>'vessel_row_count' IS NULL OR p_coverage->>'page_count' IS NULL OR (p_coverage->>'vessel_row_count')::integer<>jsonb_array_length(p_rows)
 OR jsonb_array_length(p_coverage->'pages')<>(p_coverage->>'page_count')::integer
 OR coalesce((SELECT sum((x->>'vessel_row_count')::integer) FROM jsonb_array_elements(p_coverage->'pages') x),0)<>jsonb_array_length(p_rows) THEN
  RAISE EXCEPTION 'Incomplete document coverage'; END IF;
 IF EXISTS(SELECT 1 FROM jsonb_array_elements(p_coverage->'pages') x WHERE x->>'complete' IS DISTINCT FROM 'true') THEN
  RAISE EXCEPTION 'Incomplete page'; END IF;
 IF nullif(p_instrument->>'scope_text','') IS NOT NULL THEN
  IF nullif(p_instrument->>'evidence_excerpt','') IS NULL THEN RAISE EXCEPTION 'Restriction needs source excerpt'; END IF;
  INSERT INTO public.pc_document_access_measures(document_id,authority_name,circular_reference,jurisdiction,
   issue_date,effective_from,effective_to,restriction_type,scope_text,legal_basis,evidence_excerpt,metadata)
  VALUES(p_document_id,p_instrument->>'authority_name',p_instrument->>'circular_reference',p_instrument->>'jurisdiction',
   nullif(p_instrument->>'issue_date','')::date,nullif(p_instrument->>'effective_from','')::date,
   nullif(p_instrument->>'effective_to','')::date,coalesce(p_instrument->>'restriction_type','port_access'),
   p_instrument->>'scope_text',p_instrument->>'legal_basis',p_instrument->>'evidence_excerpt',p_instrument)
  ON CONFLICT(document_id) DO NOTHING;
 END IF;
 FOR r IN SELECT value FROM jsonb_array_elements(p_rows) LOOP
  rownum:=rownum+1; vid:=NULL;
  IF nullif(r->>'name','') IS NULL OR NOT EXISTS(SELECT 1 FROM jsonb_array_elements(p_coverage->'pages') x
    WHERE (x->>'page_number')::integer=(r->>'page_number')::integer) THEN RAISE EXCEPTION 'Invalid source row'; END IF;
  row_key_value:=lpad(rownum::text,8,'0');
  imo_value:=trim(coalesce(r->>'imo','')); checksum:=0;
  IF imo_value ~ '^[0-9]{7}$' THEN
   FOR k IN 1..6 LOOP checksum:=checksum+substring(imo_value,k,1)::integer*(8-k); END LOOP;
  END IF;
  IF (CASE WHEN imo_value ~ '^[0-9]{7}$' THEN checksum%10<>right(imo_value,1)::integer ELSE true END) THEN
   state:='held_invalid_imo'; held:=held+1;
  ELSE
   -- Prevent two simultaneous imports creating the same new IMO.
   PERFORM pg_advisory_xact_lock(hashtextextended('pc_document_imo:'||imo_value,0));
   SELECT array_agg(mobile_asset_id) INTO vessel_ids FROM public.pc_mobile_assets WHERE trim(imo)=imo_value;
   IF coalesce(array_length(vessel_ids,1),0)>1 THEN
    state:='held_ambiguous_imo'; held:=held+1;
   ELSIF coalesce(array_length(vessel_ids,1),0)=1 THEN
    vid:=vessel_ids[1]; state:='matched_imo'; matched:=matched+1;
    -- Existing current identity/flag remain authoritative. The document is a dated observation.
   ELSE
    vid:='MOBILE_IMO_'||imo_value;
    INSERT INTO public.pc_mobile_assets(mobile_asset_id,name,asset_type,subtype,imo,flag,metadata)
    VALUES(vid,r->>'name','vessel',r->>'vessel_type',imo_value,nullif(r->>'flag',''),
     jsonb_build_object('created_by','document_vessels_v1','identity_source_document_id',p_document_id,
      'flag_source_document_id',p_document_id,'ownership_research_required',true));
    state:='created_imo'; created:=created+1;
   END IF;
  END IF;
  INSERT INTO public.pc_document_vessel_observations(document_id,row_key,page_number,mobile_asset_id,resolution_status,raw_record)
  VALUES(p_document_id,row_key_value,(r->>'page_number')::integer,vid,state,r)
  ON CONFLICT(document_id,row_key) DO UPDATE SET mobile_asset_id=excluded.mobile_asset_id,
   resolution_status=excluded.resolution_status,raw_record=excluded.raw_record;
  IF vid IS NOT NULL THEN
   IF jsonb_array_length(coalesce(r->'research_gaps','[]'::jsonb))>0 THEN
    INSERT INTO public.pc_document_vessel_research_queue(document_id,row_key,mobile_asset_id,imo,research_gaps)
    VALUES(p_document_id,row_key_value,vid,imo_value,r->'research_gaps') ON CONFLICT(document_id,row_key) DO NOTHING;
   END IF;
   INSERT INTO public.pc_document_links(document_link_id,document_id,linked_type,linked_id,relationship,metadata)
   VALUES(md5(p_document_id::text||':mobile_asset:'||vid)::uuid,p_document_id,'mobile_asset',vid,'source_for',
     jsonb_build_object('match_method','exact_imo','imo',imo_value)) ON CONFLICT(document_link_id) DO NOTHING;
   IF to_regclass('public.pc_vessel_identity_history') IS NOT NULL THEN
    INSERT INTO public.pc_vessel_identity_history(mobile_asset_id,identifier_type,identifier_value,
     verification_status,change_reason,metadata)
    SELECT vid,v.kind,v.value,'reported','Listed in source document; effective date not stated',
      jsonb_build_object('document_id',p_document_id,'page_number',r->'page_number','source_observation',true)
    FROM (VALUES('name',r->>'name'),('flag',r->>'flag')) v(kind,value)
    WHERE nullif(v.value,'') IS NOT NULL AND NOT EXISTS (
      SELECT 1 FROM public.pc_vessel_identity_history h WHERE h.mobile_asset_id=vid
       AND h.identifier_type=v.kind AND h.identifier_value=v.value AND h.metadata->>'document_id'=p_document_id::text);
   END IF;
   -- Ownership roles only become graph edges when explicitly evidenced and unambiguously resolved.
   FOREACH owner_role IN ARRAY ARRAY['registered_owner','beneficial_owner','operator','ism_manager'] LOOP
    owner_name:=nullif(trim(r->>owner_role),'');
    IF owner_name IS NOT NULL AND nullif(r->>'ownership_evidence','') IS NOT NULL THEN
     SELECT array_agg(entity_id) INTO entity_ids FROM public.pc_entities WHERE lower(trim(name))=lower(owner_name);
     IF array_length(entity_ids,1)=1 THEN
      rid:='REL_DOC_'||md5(p_document_id::text||vid||owner_role||entity_ids[1]);
      INSERT INTO public.pc_relationships(relationship_id,source_type,source_id,relationship_type,target_type,target_id,notes,metadata)
      VALUES(rid,'entity',entity_ids[1],owner_role,'mobile_asset',vid,r->>'ownership_evidence',
       jsonb_build_object('document_id',p_document_id,'page_number',r->'page_number','source_name',owner_name))
      ON CONFLICT(relationship_id) DO NOTHING;
     END IF;
    END IF;
   END LOOP;
  END IF;
 END LOOP;
 -- Keep the shared search index current without rebuilding it for every import.
 IF to_regclass('public.pc_terminal_object_index') IS NOT NULL THEN
  INSERT INTO public.pc_terminal_object_index(object_type,object_id,display_name,subtype,country,search_text,source_table,record_data)
  SELECT 'mobile_asset',m.mobile_asset_id,m.name,m.subtype,m.flag,
   concat_ws(' ',m.name,m.imo,m.flag,string_agg(o.raw_record->>'name',' ')), 'pc_mobile_assets',to_jsonb(m)
  FROM public.pc_mobile_assets m JOIN public.pc_document_vessel_observations o USING(mobile_asset_id)
  WHERE m.mobile_asset_id IN (SELECT mobile_asset_id FROM public.pc_document_vessel_observations WHERE document_id=p_document_id) GROUP BY m.mobile_asset_id
  ON CONFLICT(object_type,object_id) DO UPDATE SET search_text=excluded.search_text,record_data=excluded.record_data,refreshed_at=now();
  INSERT INTO public.pc_terminal_object_index(object_type,object_id,display_name,subtype,search_text,source_table,record_data)
  SELECT 'document',document_id::text,title,document_type,concat_ws(' ',title,search_text),'pc_documents',to_jsonb(x)
  FROM public.pc_documents x WHERE document_id=p_document_id
  ON CONFLICT(object_type,object_id) DO UPDATE SET display_name=excluded.display_name,search_text=excluded.search_text,record_data=excluded.record_data,refreshed_at=now();
 END IF;
 IF to_regclass('public.pc_terminal_link_index') IS NOT NULL THEN
  INSERT INTO public.pc_terminal_link_index(link_key,source_type,source_id,target_type,target_id,relation_type,relation_family,source_table,source_record_id,metadata)
  SELECT 'document_vessel:'||p_document_id::text||':'||o.mobile_asset_id,'document',p_document_id::text,
   'mobile_asset',o.mobile_asset_id,'source_for','document','pc_document_links',l.document_link_id::text,l.metadata
  FROM public.pc_document_vessel_observations o JOIN public.pc_document_links l ON l.document_id=o.document_id
   AND l.linked_id=o.mobile_asset_id AND l.linked_type='mobile_asset'
  WHERE o.document_id=p_document_id AND o.mobile_asset_id IS NOT NULL
  GROUP BY o.mobile_asset_id,l.document_link_id,l.metadata
  ON CONFLICT(link_key) DO NOTHING;
 END IF;
 UPDATE public.pc_documents SET extraction_status=CASE WHEN held>0 THEN 'extracted_with_identity_holds' ELSE 'extracted' END,
  metadata=coalesce(metadata,'{}')||jsonb_build_object('vessel_extraction_coverage',p_coverage,
     'vessel_extraction_version','document_vessels_v1'),updated_at=now() WHERE document_id=p_document_id;
 RETURN jsonb_build_object('document_id',p_document_id,'source_rows',rownum,'matched',matched,'created',created,'held',held);
END $$;
REVOKE ALL ON FUNCTION public.pc_apply_document_vessel_evidence(uuid,jsonb,jsonb,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.pc_apply_document_vessel_evidence(uuid,jsonb,jsonb,jsonb) TO service_role,postgres;
ALTER TABLE public.pc_document_vessel_observations ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pc_document_access_measures ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.pc_document_vessel_observations,public.pc_document_access_measures FROM PUBLIC,anon,authenticated;
GRANT SELECT ON public.pc_document_vessel_observations,public.pc_document_access_measures TO service_role,postgres;
CREATE OR REPLACE VIEW public.pc_v_document_vessel_access AS
SELECT o.document_id,o.mobile_asset_id,o.page_number,o.raw_record,o.resolution_status,
 m.name,m.imo,m.flag,a.authority_name,a.circular_reference,a.jurisdiction,a.scope_text,
 a.issue_date,a.effective_from,a.effective_to,a.status,d.title,d.storage_path,d.file_sha256
FROM public.pc_document_vessel_observations o
JOIN public.pc_documents d USING(document_id)
LEFT JOIN public.pc_mobile_assets m USING(mobile_asset_id)
LEFT JOIN public.pc_document_access_measures a USING(document_id);
REVOKE ALL ON public.pc_v_document_vessel_access FROM PUBLIC,anon,authenticated;
GRANT SELECT ON public.pc_v_document_vessel_access TO service_role,postgres;
NOTIFY pgrst,'reload schema';
COMMIT;
