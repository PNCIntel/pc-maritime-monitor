-- v1.7 ADDITIVE: time-dependent access/restriction intelligence in the shared P&C database.
-- Run after existing v1.4/v1.6 migrations. The source claim is NOT regulatory proof.
BEGIN;
CREATE TABLE IF NOT EXISTS public.pc_v17_restriction_batches (
 batch_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 source_sha256 text NOT NULL UNIQUE,
 label text NOT NULL,
 source_text text NOT NULL,
 input_urls jsonb NOT NULL DEFAULT '[]'::jsonb,
 status text NOT NULL DEFAULT 'saved' CHECK(status IN ('saved','researched','reviewed')),
 research_result jsonb NOT NULL DEFAULT '{}'::jsonb,
 research_urls jsonb NOT NULL DEFAULT '[]'::jsonb,
 error_text text,
 created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS public.pc_v17_restrictions (
 restriction_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 batch_id uuid NOT NULL REFERENCES public.pc_v17_restriction_batches(batch_id),
 record_key text NOT NULL UNIQUE,
 jurisdiction text NOT NULL,
 authority_name text,
 restriction_type text NOT NULL CHECK(restriction_type IN
  ('carrier_operating','airport_access','airspace_overflight','route_suspension','ground_handling',
   'port_access','maritime_exclusion','rail_access','road_border','sanctions','other')),
 scope_text text NOT NULL,
 affected_operator_names jsonb NOT NULL DEFAULT '[]'::jsonb,
 affected_location_names jsonb NOT NULL DEFAULT '[]'::jsonb,
 effective_from date,effective_to date,date_precision text NOT NULL DEFAULT 'unknown'
   CHECK(date_precision IN ('day','month','unknown')),
 status text NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','researched','needs_review','published','lifted','superseded')),
 evidence_status text NOT NULL DEFAULT 'reported' CHECK(evidence_status IN ('reported','corroborated','official')),
 evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
 fact_summary text NOT NULL,commercial_implications text,operational_implications text,
 monitoring_indicators jsonb NOT NULL DEFAULT '[]'::jsonb,
 restrictions_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
 reviewed_by text,published_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now(),
 CONSTRAINT pc_v17_valid_date_range CHECK(effective_to IS NULL OR effective_from IS NULL OR effective_to>=effective_from)
);
CREATE INDEX IF NOT EXISTS pc_v17_restrict_batch_idx ON public.pc_v17_restrictions(batch_id,status);
CREATE INDEX IF NOT EXISTS pc_v17_restrict_jurisdiction_idx ON public.pc_v17_restrictions(jurisdiction,status,effective_from);
CREATE TABLE IF NOT EXISTS public.pc_v17_restriction_links (
 link_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 restriction_id uuid NOT NULL REFERENCES public.pc_v17_restrictions(restriction_id) ON DELETE CASCADE,
 entity_id text REFERENCES public.pc_entities(entity_id),
 asset_id text REFERENCES public.pc_assets(asset_id),
 mobile_asset_id text REFERENCES public.pc_mobile_assets(mobile_asset_id),
 relationship text NOT NULL CHECK(relationship IN ('issuing_authority','affected_operator','affected_location','affected_asset','mentioned')),
 evidence_url text NOT NULL,
 CHECK(num_nonnulls(entity_id,asset_id,mobile_asset_id)=1)
);
CREATE UNIQUE INDEX IF NOT EXISTS pc_v17_links_entity_uq ON public.pc_v17_restriction_links(restriction_id,relationship,entity_id) WHERE entity_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS pc_v17_links_asset_uq ON public.pc_v17_restriction_links(restriction_id,relationship,asset_id) WHERE asset_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS pc_v17_links_mobile_uq ON public.pc_v17_restriction_links(restriction_id,relationship,mobile_asset_id) WHERE mobile_asset_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS pc_v17_links_entity_idx ON public.pc_v17_restriction_links(entity_id) WHERE entity_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS pc_v17_links_asset_idx ON public.pc_v17_restriction_links(asset_id) WHERE asset_id IS NOT NULL;
CREATE TABLE IF NOT EXISTS public.pc_v17_publication_snapshots (
 snapshot_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 restriction_id uuid NOT NULL UNIQUE REFERENCES public.pc_v17_restrictions(restriction_id),
 prepublication_record jsonb NOT NULL,
 reviewed_by text NOT NULL,
 saved_at timestamptz NOT NULL DEFAULT now()
);
-- One atomic, service-role-only publication. Existing canonical IDs are validated by FK.
CREATE OR REPLACE FUNCTION public.pc_v17_publish_restriction(
 p_restriction uuid,p_reviewer text,p_allow_reported boolean,p_links jsonb DEFAULT '[]'::jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=public,pg_temp AS $$
DECLARE r public.pc_v17_restrictions%ROWTYPE; l jsonb; n integer := 0; url text; rel text;
BEGIN
 SELECT * INTO r FROM public.pc_v17_restrictions WHERE restriction_id=p_restriction FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Restriction not found'; END IF;
 IF r.status NOT IN ('researched','needs_review','draft','published') THEN
  RAISE EXCEPTION 'Cannot publish restriction in status %',r.status; END IF;
 IF jsonb_typeof(r.evidence)<>'array' OR jsonb_array_length(r.evidence)=0 THEN
  RAISE EXCEPTION 'No source-backed evidence attached'; END IF;
 IF r.evidence_status='reported' AND NOT p_allow_reported THEN
  RAISE EXCEPTION 'Reported claim requires explicit reported-status review'; END IF;
 IF nullif(trim(p_reviewer),'') IS NULL THEN RAISE EXCEPTION 'Reviewer required'; END IF;
 IF jsonb_typeof(p_links)<>'array' OR jsonb_array_length(p_links)>50 THEN
  RAISE EXCEPTION 'Invalid relationship batch'; END IF;
 FOR l IN SELECT value FROM jsonb_array_elements(p_links) LOOP
  url := l->>'evidence_url'; rel := l->>'relationship';
  IF url IS NULL OR NOT EXISTS (SELECT 1 FROM jsonb_array_elements(r.evidence) e WHERE e->>'url'=url) THEN
   RAISE EXCEPTION 'Relationship source URL must be present in approved evidence'; END IF;
  IF rel NOT IN ('issuing_authority','affected_operator','affected_location','affected_asset','mentioned') THEN
   RAISE EXCEPTION 'Unsupported link role'; END IF;
  IF (l->>'entity_id') IS NOT NULL THEN
   INSERT INTO public.pc_v17_restriction_links(restriction_id,entity_id,relationship,evidence_url)
   VALUES(p_restriction,l->>'entity_id',rel,url) ON CONFLICT DO NOTHING;
  ELSIF (l->>'asset_id') IS NOT NULL THEN
   INSERT INTO public.pc_v17_restriction_links(restriction_id,asset_id,relationship,evidence_url)
   VALUES(p_restriction,l->>'asset_id',rel,url) ON CONFLICT DO NOTHING;
  ELSIF (l->>'mobile_asset_id') IS NOT NULL THEN
   INSERT INTO public.pc_v17_restriction_links(restriction_id,mobile_asset_id,relationship,evidence_url)
   VALUES(p_restriction,l->>'mobile_asset_id',rel,url) ON CONFLICT DO NOTHING;
  ELSE RAISE EXCEPTION 'Canonical endpoint required'; END IF;
  n := n+1;
 END LOOP;
 IF r.status<>'published' THEN
  INSERT INTO public.pc_v17_publication_snapshots(restriction_id,prepublication_record,reviewed_by)
  VALUES(p_restriction,to_jsonb(r),p_reviewer) ON CONFLICT(restriction_id) DO NOTHING;
 END IF;
 UPDATE public.pc_v17_restrictions
 SET status='published',reviewed_by=p_reviewer,
     published_at=coalesce(published_at,now()),updated_at=now()
 WHERE restriction_id=p_restriction;
 RETURN jsonb_build_object('restriction_id',p_restriction,'status','published',
     'confirmed_links',n,'evidence_status',r.evidence_status);
END $$;
REVOKE ALL ON FUNCTION public.pc_v17_publish_restriction(uuid,text,boolean,jsonb) FROM PUBLIC,anon,authenticated;
GRANT EXECUTE ON FUNCTION public.pc_v17_publish_restriction(uuid,text,boolean,jsonb) TO service_role,postgres;
ALTER TABLE public.pc_v17_restriction_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pc_v17_restrictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pc_v17_restriction_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pc_v17_publication_snapshots ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.pc_v17_restriction_batches,public.pc_v17_restrictions,public.pc_v17_restriction_links,public.pc_v17_publication_snapshots FROM PUBLIC,anon,authenticated;
GRANT SELECT,INSERT,UPDATE ON public.pc_v17_restriction_batches,public.pc_v17_restrictions TO service_role,postgres;
GRANT SELECT,INSERT ON public.pc_v17_restriction_links TO service_role,postgres;
GRANT DELETE ON public.pc_v17_restriction_links TO service_role,postgres;
GRANT SELECT,INSERT ON public.pc_v17_publication_snapshots TO service_role,postgres;
CREATE OR REPLACE VIEW public.pc_v17_live_restrictions AS
 SELECT restriction_id,jurisdiction,authority_name,restriction_type,scope_text,affected_operator_names,
 affected_location_names,effective_from,effective_to,date_precision,evidence_status,evidence,fact_summary,
 commercial_implications,operational_implications,monitoring_indicators,status,published_at
 FROM public.pc_v17_restrictions WHERE status IN ('published','lifted','superseded');
REVOKE ALL ON public.pc_v17_live_restrictions FROM PUBLIC,anon,authenticated;
GRANT SELECT ON public.pc_v17_live_restrictions TO service_role,postgres;
NOTIFY pgrst,'reload schema';
COMMIT;
