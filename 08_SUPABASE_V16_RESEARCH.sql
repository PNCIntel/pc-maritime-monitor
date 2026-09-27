-- Additive, service-role-only, durable research and reversible stage repair.
BEGIN;
CREATE TABLE IF NOT EXISTS public.pc_v16_research_tasks (
  task_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ingestion_job_id uuid NOT NULL REFERENCES public.pc_ingestion_jobs(ingestion_job_id),
  staged_record_id uuid NOT NULL UNIQUE REFERENCES public.pc_staged_records(staged_record_id),
  status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','running','researched','applied','held','failed')),
  attempts integer NOT NULL DEFAULT 0,
  request jsonb NOT NULL DEFAULT '{}'::jsonb,
  result jsonb NOT NULL DEFAULT '{}'::jsonb,
  error_text text,
  updated_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS pc_v16_research_job_idx ON public.pc_v16_research_tasks(ingestion_job_id,status);
CREATE TABLE IF NOT EXISTS public.pc_v16_stage_revisions (
  revision_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  task_id uuid NOT NULL REFERENCES public.pc_v16_research_tasks(task_id),
  staged_record_id uuid NOT NULL REFERENCES public.pc_staged_records(staged_record_id),
  old_table text NOT NULL, old_natural_key text NOT NULL, old_payload jsonb NOT NULL,
  new_table text NOT NULL, new_natural_key text NOT NULL, new_payload jsonb NOT NULL,
  research_evidence jsonb NOT NULL, applied_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(task_id,staged_record_id)
);
CREATE TABLE IF NOT EXISTS public.pc_v16_verified_bindings (
  staged_record_id uuid PRIMARY KEY REFERENCES public.pc_staged_records(staged_record_id),
  ingestion_job_id uuid NOT NULL REFERENCES public.pc_ingestion_jobs(ingestion_job_id),
  research_task_id uuid NOT NULL REFERENCES public.pc_v16_research_tasks(task_id),
  canonical_table text NOT NULL CHECK(canonical_table IN ('pc_entities','pc_assets','pc_mobile_assets')),
  canonical_id text NOT NULL,
  evidence jsonb NOT NULL,
  verified_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.pc_v16_relationship_candidates (
  candidate_key text PRIMARY KEY,
  task_id uuid NOT NULL REFERENCES public.pc_v16_research_tasks(task_id),
  event_stage_id uuid NOT NULL REFERENCES public.pc_staged_records(staged_record_id),
  ingestion_job_id uuid NOT NULL REFERENCES public.pc_ingestion_jobs(ingestion_job_id),
  linked_type text NOT NULL CHECK(linked_type IN ('entity','asset','mobile_asset')),
  linked_name text NOT NULL,
  relationship text NOT NULL,
  evidence_url text NOT NULL,
  status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','linked','held')),
  staged_link_id uuid REFERENCES public.pc_staged_records(staged_record_id),
  reason text,
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS pc_v16_link_candidates_job_idx ON public.pc_v16_relationship_candidates(ingestion_job_id,status);
ALTER TABLE public.pc_v16_research_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pc_v16_stage_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pc_v16_relationship_candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pc_v16_verified_bindings ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.pc_v16_research_tasks,public.pc_v16_stage_revisions,public.pc_v16_relationship_candidates,public.pc_v16_verified_bindings FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON public.pc_v16_research_tasks TO service_role,postgres;
GRANT SELECT,INSERT ON public.pc_v16_stage_revisions TO service_role,postgres;
GRANT SELECT,INSERT,UPDATE ON public.pc_v16_relationship_candidates TO service_role,postgres;
GRANT SELECT,INSERT,UPDATE ON public.pc_v16_verified_bindings TO service_role,postgres;

CREATE OR REPLACE FUNCTION public.pc_v16_apply_repair(
 p_task uuid, p_original_table text, p_original_payload jsonb,
 p_new_table text, p_new_name text, p_new_payload jsonb, p_evidence jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE t record;s record;
BEGIN
 SELECT * INTO t FROM public.pc_v16_research_tasks WHERE task_id=p_task FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Research task not found';END IF;
 SELECT * INTO s FROM public.pc_staged_records WHERE staged_record_id=t.staged_record_id FOR UPDATE;
 IF NOT FOUND OR s.ingestion_job_id<>t.ingestion_job_id THEN RAISE EXCEPTION 'Stage record not found in task job';END IF;
 IF EXISTS(SELECT 1 FROM public.pc_v10_publication_items WHERE staged_record_id=s.staged_record_id)
 THEN RAISE EXCEPTION 'Already published; do not rewrite canonical history'; END IF;
 IF t.status='applied' THEN RETURN jsonb_build_object('status','already_applied','staged_record_id',s.staged_record_id);END IF;
 IF t.status<>'researched' THEN RAISE EXCEPTION 'Research must be complete before stage repair';END IF;
 IF s.target_table<>p_original_table OR s.payload<>p_original_payload
 THEN RAISE EXCEPTION 'Stage record changed; research must be refreshed';END IF;
 IF p_new_table NOT IN ('pc_entities','pc_assets','pc_mobile_assets','pc_events')
 THEN RAISE EXCEPTION 'Unsupported repaired target';END IF;
 IF nullif(trim(p_new_name),'') IS NULL OR jsonb_typeof(p_new_payload)<>'object'
 THEN RAISE EXCEPTION 'Invalid repaired record';END IF;
 IF coalesce(jsonb_array_length(CASE WHEN jsonb_typeof(p_evidence)='array' THEN p_evidence ELSE '[]'::jsonb END),0)<1
 THEN RAISE EXCEPTION 'Research evidence required';END IF;
 INSERT INTO public.pc_v16_stage_revisions(task_id,staged_record_id,old_table,old_natural_key,old_payload,new_table,new_natural_key,new_payload,research_evidence)
 VALUES(t.task_id,s.staged_record_id,s.target_table,s.natural_key,s.payload,p_new_table,p_new_name,p_new_payload,p_evidence)
 ON CONFLICT(task_id,staged_record_id) DO NOTHING;
 DELETE FROM public.pc_v10_approvals WHERE staged_record_id=s.staged_record_id;
 UPDATE public.pc_staged_records SET target_table=p_new_table,natural_key=p_new_name,payload=p_new_payload,
   resolution_status='UNRESOLVED',resolved_entity_id=NULL,resolution_method='v1.6 AI research: canonical recheck required',
   resolution_details=coalesce(s.resolution_details,'{}'::jsonb)||jsonb_build_object('v16_repair_task_id',t.task_id::text,'v16_researched',true),
   review_status='pending',validation_status='pending'
 WHERE staged_record_id=s.staged_record_id;
 UPDATE public.pc_v16_research_tasks SET status='applied',updated_at=now() WHERE task_id=t.task_id;
 RETURN jsonb_build_object('status','applied','staged_record_id',s.staged_record_id,'target_table',p_new_table);
END $$;
REVOKE ALL ON FUNCTION public.pc_v16_apply_repair(uuid,text,jsonb,text,text,jsonb,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.pc_v16_apply_repair(uuid,text,jsonb,text,text,jsonb,jsonb) TO service_role,postgres;
NOTIFY pgrst,'reload schema';
COMMIT;
