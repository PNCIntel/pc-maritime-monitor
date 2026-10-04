-- POWER & CORRIDORS | TERMINAL READ MODEL / CROSS-DOMAIN INDEX
-- Purpose: one fast, shared read layer for Trade, Intelligence, Sanctions and Strategic Industries.
-- Safe/additive: source-of-truth tables remain authoritative; these are derived support tables.
BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS public.pc_terminal_object_index (
  object_type text NOT NULL,
  object_id text NOT NULL,
  display_name text NOT NULL,
  subtype text,
  country text,
  region text,
  status text,
  search_text text NOT NULL DEFAULT '',
  source_table text NOT NULL,
  record_data jsonb NOT NULL DEFAULT '{}'::jsonb,
  refreshed_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (object_type, object_id)
);

CREATE INDEX IF NOT EXISTS idx_pc_terminal_object_name
  ON public.pc_terminal_object_index (lower(display_name));
CREATE INDEX IF NOT EXISTS idx_pc_terminal_object_type
  ON public.pc_terminal_object_index (object_type, subtype);
CREATE INDEX IF NOT EXISTS idx_pc_terminal_object_search_trgm
  ON public.pc_terminal_object_index USING gin (search_text gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_pc_terminal_object_display_trgm
  ON public.pc_terminal_object_index USING gin (display_name gin_trgm_ops);

CREATE TABLE IF NOT EXISTS public.pc_terminal_link_index (
  link_key text PRIMARY KEY,
  source_type text NOT NULL,
  source_id text NOT NULL,
  target_type text NOT NULL,
  target_id text NOT NULL,
  relation_type text NOT NULL,
  relation_family text NOT NULL DEFAULT 'relationship',
  source_table text NOT NULL,
  source_record_id text,
  event_id text,
  confidence text,
  evidence_url text,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  refreshed_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pc_terminal_link_source
  ON public.pc_terminal_link_index(source_type,source_id,relation_family);
CREATE INDEX IF NOT EXISTS idx_pc_terminal_link_target
  ON public.pc_terminal_link_index(target_type,target_id,relation_family);
CREATE INDEX IF NOT EXISTS idx_pc_terminal_link_event
  ON public.pc_terminal_link_index(event_id) WHERE event_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_pc_terminal_link_family
  ON public.pc_terminal_link_index(relation_family,relation_type);

CREATE OR REPLACE VIEW public.pc_v_terminal_links AS
SELECT
  l.*,
  so.display_name AS source_name,
  so.subtype AS source_subtype,
  so.country AS source_country,
  tobj.display_name AS target_name,
  tobj.subtype AS target_subtype,
  tobj.country AS target_country
FROM public.pc_terminal_link_index l
LEFT JOIN public.pc_terminal_object_index so
  ON so.object_type=l.source_type AND so.object_id=l.source_id
LEFT JOIN public.pc_terminal_object_index tobj
  ON tobj.object_type=l.target_type AND tobj.object_id=l.target_id;

CREATE OR REPLACE VIEW public.pc_v_terminal_event_context AS
SELECT
  CASE WHEN l.source_type='event' THEN l.source_id ELSE l.target_id END AS event_id,
  CASE WHEN l.source_type='event' THEN l.target_type ELSE l.source_type END AS object_type,
  CASE WHEN l.source_type='event' THEN l.target_id ELSE l.source_id END AS object_id,
  CASE WHEN l.source_type='event' THEN l.target_name ELSE l.source_name END AS object_name,
  l.relation_type,
  l.relation_family,
  l.source_table,
  l.source_record_id,
  l.confidence,
  l.evidence_url,
  l.metadata
FROM public.pc_v_terminal_links l
WHERE l.source_type='event' OR l.target_type='event';

CREATE OR REPLACE VIEW public.pc_v_terminal_context_counts AS
SELECT object_type, object_id, relation_family, count(*)::bigint AS link_count
FROM (
  SELECT source_type AS object_type, source_id AS object_id, relation_family
  FROM public.pc_terminal_link_index
  UNION ALL
  SELECT target_type AS object_type, target_id AS object_id, relation_family
  FROM public.pc_terminal_link_index
) x
GROUP BY object_type, object_id, relation_family;

CREATE OR REPLACE FUNCTION public.pc_refresh_terminal_indexes()
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path=public
AS $$
DECLARE
  object_count bigint := 0;
  link_count bigint := 0;
BEGIN
  TRUNCATE public.pc_terminal_link_index;
  TRUNCATE public.pc_terminal_object_index;

  -- CORE SELECTABLE OBJECTS --------------------------------------------------
  IF to_regclass('public.pc_entities') IS NOT NULL THEN
    EXECUTE $q$
      INSERT INTO public.pc_terminal_object_index
      (object_type,object_id,display_name,subtype,country,region,status,search_text,source_table,record_data)
      SELECT 'entity',
             j->>'entity_id',
             coalesce(nullif(j->>'name',''),j->>'entity_id'),
             coalesce(j->>'entity_type',j->>'subtype'),
             coalesce(j->>'hq_country',j->>'country'),
             coalesce(j->>'hq_city',j->>'region',j->>'region_city'),
             coalesce(j->>'record_status',j->>'status'),
             concat_ws(' ',j->>'name',j->>'entity_type',j->>'hq_country',j->>'hq_city',j->>'website_url',j->>'description',j->>'metadata'),
             'pc_entities', j
      FROM public.pc_entities t CROSS JOIN LATERAL to_jsonb(t) j
      WHERE nullif(j->>'entity_id','') IS NOT NULL
    $q$;
  END IF;

  IF to_regclass('public.pc_assets') IS NOT NULL THEN
    EXECUTE $q$
      INSERT INTO public.pc_terminal_object_index
      (object_type,object_id,display_name,subtype,country,region,status,search_text,source_table,record_data)
      SELECT 'asset',
             j->>'asset_id',
             coalesce(nullif(j->>'name',''),j->>'asset_id'),
             coalesce(j->>'asset_type',j->>'subtype'),
             j->>'country',
             coalesce(j->>'region_city',j->>'region'),
             j->>'status',
             concat_ws(' ',j->>'name',j->>'asset_type',j->>'subtype',j->>'country',j->>'region_city',j->>'description',j->>'metadata'),
             'pc_assets', j
      FROM public.pc_assets t CROSS JOIN LATERAL to_jsonb(t) j
      WHERE nullif(j->>'asset_id','') IS NOT NULL
    $q$;
  END IF;

  IF to_regclass('public.pc_mobile_assets') IS NOT NULL THEN
    EXECUTE $q$
      INSERT INTO public.pc_terminal_object_index
      (object_type,object_id,display_name,subtype,country,region,status,search_text,source_table,record_data)
      SELECT 'mobile_asset',
             j->>'mobile_asset_id',
             coalesce(nullif(j->>'name',''),nullif(j->>'vessel_name',''),j->>'mobile_asset_id'),
             coalesce(j->>'asset_type',j->>'subtype',j->>'mobile_asset_type'),
             coalesce(j->>'flag',j->>'country'),
             j->>'region',
             j->>'status',
             concat_ws(' ',j->>'name',j->>'vessel_name',j->>'imo',j->>'mmsi',j->>'registration',j->>'call_sign',j->>'flag',j->>'asset_type',j->>'subtype',j->>'metadata'),
             'pc_mobile_assets', j
      FROM public.pc_mobile_assets t CROSS JOIN LATERAL to_jsonb(t) j
      WHERE nullif(j->>'mobile_asset_id','') IS NOT NULL
    $q$;
  END IF;

  IF to_regclass('public.pc_events') IS NOT NULL THEN
    EXECUTE $q$
      INSERT INTO public.pc_terminal_object_index
      (object_type,object_id,display_name,subtype,country,region,status,search_text,source_table,record_data)
      SELECT 'event',
             j->>'event_id',
             coalesce(nullif(j->>'title',''),j->>'event_id'),
             j->>'event_type',
             coalesce(j->>'country',j->>'primary_country'),
             coalesce(j->>'region',j->>'location'),
             coalesce(j->>'status',j->>'verification_status'),
             concat_ws(' ',j->>'title',j->>'event_type',j->>'country',j->>'region',j->>'location',j->>'description',j->>'operational_impact',j->>'commercial_impact',j->>'metadata'),
             'pc_events', j
      FROM public.pc_events t CROSS JOIN LATERAL to_jsonb(t) j
      WHERE nullif(j->>'event_id','') IS NOT NULL
    $q$;
  END IF;

  IF to_regclass('public.pc_trade_corridors') IS NOT NULL THEN
    EXECUTE $q$
      INSERT INTO public.pc_terminal_object_index
      (object_type,object_id,display_name,subtype,country,region,status,search_text,source_table,record_data)
      SELECT 'corridor',
             j->>'corridor_key',
             coalesce(nullif(j->>'corridor_name',''),j->>'corridor_key'),
             j->>'corridor_type',
             NULL,
             coalesce(j->>'origin_region',j->>'destination_region'),
             j->>'status',
             concat_ws(' ',j->>'corridor_name',j->>'corridor_type',j->>'origin_region',j->>'destination_region',j->>'geography',j->>'description',j->>'metadata'),
             'pc_trade_corridors', j
      FROM public.pc_trade_corridors t CROSS JOIN LATERAL to_jsonb(t) j
      WHERE nullif(j->>'corridor_key','') IS NOT NULL
    $q$;
  END IF;

  -- SPECIALIST OBJECTS -------------------------------------------------------
  IF to_regclass('public.pc_documents') IS NOT NULL THEN
    EXECUTE $q$
      INSERT INTO public.pc_terminal_object_index
      (object_type,object_id,display_name,subtype,country,region,status,search_text,source_table,record_data)
      SELECT 'document',
             j->>'document_id',
             coalesce(nullif(j->>'title',''),j->>'document_id'),
             j->>'document_type',
             j->>'country',
             j->>'region',
             coalesce(j->>'status',j->>'verification_status'),
             concat_ws(' ',j->>'title',j->>'document_type',j->>'source_name',j->>'publisher',j->>'summary',j->>'metadata'),
             'pc_documents', j
      FROM public.pc_documents t CROSS JOIN LATERAL to_jsonb(t) j
      WHERE nullif(j->>'document_id','') IS NOT NULL
      ON CONFLICT (object_type,object_id) DO NOTHING
    $q$;
  END IF;

  IF to_regclass('public.pc_sanctions_designations') IS NOT NULL THEN
    EXECUTE $q$
      INSERT INTO public.pc_terminal_object_index
      (object_type,object_id,display_name,subtype,country,region,status,search_text,source_table,record_data)
      SELECT 'sanction',
             j->>'sanctions_designation_id',
             coalesce(nullif(j->>'designated_name',''),nullif(j->>'subject_name',''),nullif(j->>'name',''),j->>'sanctions_designation_id'),
             coalesce(j->>'program',j->>'regime',j->>'subject_type'),
             coalesce(j->>'jurisdiction',j->>'country'),
             NULL,
             coalesce(j->>'status',j->>'designation_status'),
             concat_ws(' ',j->>'designated_name',j->>'subject_name',j->>'name',j->>'program',j->>'regime',j->>'authority',j->>'jurisdiction',j->>'aliases',j->>'metadata'),
             'pc_sanctions_designations', j
      FROM public.pc_sanctions_designations t CROSS JOIN LATERAL to_jsonb(t) j
      WHERE nullif(j->>'sanctions_designation_id','') IS NOT NULL
      ON CONFLICT (object_type,object_id) DO NOTHING
    $q$;
  END IF;

  IF to_regclass('public.pc_defence_programmes') IS NOT NULL THEN
    EXECUTE $q$
      INSERT INTO public.pc_terminal_object_index
      (object_type,object_id,display_name,subtype,country,region,status,search_text,source_table,record_data)
      SELECT 'programme',
             j->>'defence_programme_id',
             coalesce(nullif(j->>'programme_name',''),j->>'defence_programme_id'),
             j->>'programme_type',
             j->>'jurisdiction',
             NULL,
             j->>'programme_status',
             concat_ws(' ',j->>'programme_name',j->>'programme_type',j->>'programme_status',j->>'metadata'),
             'pc_defence_programmes', j
      FROM public.pc_defence_programmes t CROSS JOIN LATERAL to_jsonb(t) j
      WHERE nullif(j->>'defence_programme_id','') IS NOT NULL
      ON CONFLICT (object_type,object_id) DO NOTHING
    $q$;
  END IF;

  IF to_regclass('public.pc_security_operations') IS NOT NULL THEN
    EXECUTE $q$
      INSERT INTO public.pc_terminal_object_index
      (object_type,object_id,display_name,subtype,country,region,status,search_text,source_table,record_data)
      SELECT 'security_operation',
             j->>'security_operation_id',
             coalesce(nullif(j->>'operation_name',''),j->>'security_operation_id'),
             j->>'operation_type',
             NULL,
             j->>'operating_area',
             j->>'operation_status',
             concat_ws(' ',j->>'operation_name',j->>'operation_type',j->>'operation_status',j->>'operating_area',j->>'metadata'),
             'pc_security_operations', j
      FROM public.pc_security_operations t CROSS JOIN LATERAL to_jsonb(t) j
      WHERE nullif(j->>'security_operation_id','') IS NOT NULL
      ON CONFLICT (object_type,object_id) DO NOTHING
    $q$;
  END IF;

  -- IDENTITY ALIASES augment search text.
  IF to_regclass('public.pc_identity_aliases_v2') IS NOT NULL THEN
    EXECUTE $q$
      UPDATE public.pc_terminal_object_index o
      SET search_text = concat_ws(' ',o.search_text,a.aliases)
      FROM (
        SELECT
          CASE WHEN lower(coalesce(j->>'object_type',''))='vessel' THEN 'mobile_asset'
               ELSE lower(coalesce(j->>'object_type','')) END AS object_type,
          j->>'canonical_id' AS object_id,
          string_agg(coalesce(j->>'alias_name',''),' ') AS aliases
        FROM public.pc_identity_aliases_v2 t CROSS JOIN LATERAL to_jsonb(t) j
        GROUP BY 1,2
      ) a
      WHERE o.object_type=a.object_type AND o.object_id=a.object_id
    $q$;
  END IF;

  -- CROSS-DOMAIN LINKS -------------------------------------------------------

  IF to_regclass('public.pc_relationships') IS NOT NULL THEN
    EXECUTE $q$
      INSERT INTO public.pc_terminal_link_index
      (link_key,source_type,source_id,target_type,target_id,relation_type,relation_family,source_table,source_record_id,event_id,confidence,evidence_url,metadata)
      SELECT md5(concat_ws('|','pc_relationships',coalesce(j->>'relationship_id',''),j->>'source_type',j->>'source_id',j->>'relationship_type',j->>'target_type',j->>'target_id')),
             CASE WHEN lower(j->>'source_type')='vessel' THEN 'mobile_asset' ELSE lower(j->>'source_type') END,
             j->>'source_id',
             CASE WHEN lower(j->>'target_type')='vessel' THEN 'mobile_asset' ELSE lower(j->>'target_type') END,
             j->>'target_id',
             coalesce(nullif(j->>'relationship_type',''),'related_to'),
             'relationship',
             'pc_relationships',
             j->>'relationship_id',
             NULL,
             j->>'confidence',
             j->>'source_url',
             j
      FROM public.pc_relationships t CROSS JOIN LATERAL to_jsonb(t) j
      WHERE nullif(j->>'source_id','') IS NOT NULL AND nullif(j->>'target_id','') IS NOT NULL
      ON CONFLICT (link_key) DO NOTHING
    $q$;
  END IF;

  IF to_regclass('public.pc_event_links') IS NOT NULL THEN
    EXECUTE $q$
      INSERT INTO public.pc_terminal_link_index
      (link_key,source_type,source_id,target_type,target_id,relation_type,relation_family,source_table,source_record_id,event_id,confidence,evidence_url,metadata)
      SELECT md5(concat_ws('|','pc_event_links',j->>'event_id',j->>'linked_type',j->>'linked_id',j->>'relationship')),
             'event',
             j->>'event_id',
             CASE WHEN lower(j->>'linked_type')='vessel' THEN 'mobile_asset' ELSE lower(j->>'linked_type') END,
             j->>'linked_id',
             coalesce(nullif(j->>'relationship',''),'involves'),
             'event_context',
             'pc_event_links',
             coalesce(j->>'event_link_id',j->>'id'),
             j->>'event_id',
             j->>'confidence',
             j->>'source_url',
             j
      FROM public.pc_event_links t CROSS JOIN LATERAL to_jsonb(t) j
      WHERE nullif(j->>'event_id','') IS NOT NULL AND nullif(j->>'linked_id','') IS NOT NULL
      ON CONFLICT (link_key) DO NOTHING
    $q$;
  END IF;

  IF to_regclass('public.pc_company_asset_roles') IS NOT NULL THEN
    EXECUTE $q$
      INSERT INTO public.pc_terminal_link_index
      (link_key,source_type,source_id,target_type,target_id,relation_type,relation_family,source_table,source_record_id,confidence,evidence_url,metadata)
      SELECT md5(concat_ws('|','pc_company_asset_roles',j->>'entity_id',coalesce(j->>'asset_id',j->>'mobile_asset_id'),j->>'asset_role')),
             'entity',
             j->>'entity_id',
             CASE WHEN nullif(j->>'mobile_asset_id','') IS NOT NULL THEN 'mobile_asset' ELSE 'asset' END,
             coalesce(nullif(j->>'mobile_asset_id',''),j->>'asset_id'),
             coalesce(nullif(j->>'asset_role',''),'associated_with'),
             'asset_role',
             'pc_company_asset_roles',
             coalesce(j->>'company_asset_role_id',j->>'id'),
             j->>'confidence',
             j->>'source_url',
             j
      FROM public.pc_company_asset_roles t CROSS JOIN LATERAL to_jsonb(t) j
      WHERE nullif(j->>'entity_id','') IS NOT NULL
        AND coalesce(nullif(j->>'mobile_asset_id',''),nullif(j->>'asset_id','')) IS NOT NULL
      ON CONFLICT (link_key) DO NOTHING
    $q$;
  END IF;

  IF to_regclass('public.pc_company_corridor_roles') IS NOT NULL THEN
    EXECUTE $q$
      INSERT INTO public.pc_terminal_link_index
      (link_key,source_type,source_id,target_type,target_id,relation_type,relation_family,source_table,source_record_id,confidence,evidence_url,metadata)
      SELECT md5(concat_ws('|','pc_company_corridor_roles',j->>'entity_id',j->>'corridor_key',j->>'corridor_role')),
             'entity',j->>'entity_id','corridor',j->>'corridor_key',
             coalesce(nullif(j->>'corridor_role',''),'participates_in'),
             'corridor_role','pc_company_corridor_roles',
             coalesce(j->>'company_corridor_role_id',j->>'id'),
             j->>'confidence',j->>'source_url',j
      FROM public.pc_company_corridor_roles t CROSS JOIN LATERAL to_jsonb(t) j
      WHERE nullif(j->>'entity_id','') IS NOT NULL AND nullif(j->>'corridor_key','') IS NOT NULL
      ON CONFLICT (link_key) DO NOTHING
    $q$;
  END IF;

  IF to_regclass('public.pc_company_portfolio_positions') IS NOT NULL THEN
    EXECUTE $q$
      INSERT INTO public.pc_terminal_link_index
      (link_key,source_type,source_id,target_type,target_id,relation_type,relation_family,source_table,source_record_id,confidence,evidence_url,metadata)
      SELECT md5(concat_ws('|','pc_company_portfolio_positions',j->>'holder_entity_id',coalesce(j->>'investee_entity_id',j->>'investee_asset_id'),coalesce(j->>'position_type',j->>'role'))),
             'entity',j->>'holder_entity_id',
             CASE WHEN nullif(j->>'investee_entity_id','') IS NOT NULL THEN 'entity' ELSE 'asset' END,
             coalesce(nullif(j->>'investee_entity_id',''),j->>'investee_asset_id'),
             coalesce(nullif(j->>'position_type',''),nullif(j->>'role',''),'portfolio_position'),
             'portfolio','pc_company_portfolio_positions',
             coalesce(j->>'portfolio_position_id',j->>'id'),
             j->>'confidence',j->>'source_url',j
      FROM public.pc_company_portfolio_positions t CROSS JOIN LATERAL to_jsonb(t) j
      WHERE nullif(j->>'holder_entity_id','') IS NOT NULL
        AND coalesce(nullif(j->>'investee_entity_id',''),nullif(j->>'investee_asset_id','')) IS NOT NULL
      ON CONFLICT (link_key) DO NOTHING
    $q$;
  END IF;

  IF to_regclass('public.pc_document_entity_links') IS NOT NULL THEN
    EXECUTE $q$
      INSERT INTO public.pc_terminal_link_index
      (link_key,source_type,source_id,target_type,target_id,relation_type,relation_family,source_table,source_record_id,confidence,evidence_url,metadata)
      SELECT md5(concat_ws('|','pc_document_entity_links',j->>'entity_id',j->>'document_id',j->>'relationship')),
             'entity',j->>'entity_id','document',j->>'document_id',
             coalesce(nullif(j->>'relationship',''),'mentioned_in'),
             'evidence','pc_document_entity_links',
             coalesce(j->>'document_entity_link_id',j->>'id'),
             j->>'confidence',j->>'source_url',j
      FROM public.pc_document_entity_links t CROSS JOIN LATERAL to_jsonb(t) j
      WHERE nullif(j->>'entity_id','') IS NOT NULL AND nullif(j->>'document_id','') IS NOT NULL
      ON CONFLICT (link_key) DO NOTHING
    $q$;
  END IF;

  IF to_regclass('public.pc_sanctions_designations') IS NOT NULL THEN
    EXECUTE $q$
      INSERT INTO public.pc_terminal_link_index
      (link_key,source_type,source_id,target_type,target_id,relation_type,relation_family,source_table,source_record_id,confidence,evidence_url,metadata)
      SELECT md5(concat_ws('|','pc_sanctions_designations',j->>'sanctions_designation_id',coalesce(j->>'entity_id',j->>'mobile_asset_id'))),
             'sanction',j->>'sanctions_designation_id',
             CASE WHEN nullif(j->>'mobile_asset_id','') IS NOT NULL THEN 'mobile_asset' ELSE 'entity' END,
             coalesce(nullif(j->>'mobile_asset_id',''),j->>'entity_id'),
             'designates','sanctions','pc_sanctions_designations',
             j->>'sanctions_designation_id',j->>'confidence',j->>'source_url',j
      FROM public.pc_sanctions_designations t CROSS JOIN LATERAL to_jsonb(t) j
      WHERE coalesce(nullif(j->>'mobile_asset_id',''),nullif(j->>'entity_id','')) IS NOT NULL
      ON CONFLICT (link_key) DO NOTHING
    $q$;
  END IF;

  IF to_regclass('public.pc_defence_programmes') IS NOT NULL THEN
    EXECUTE $q$
      INSERT INTO public.pc_terminal_link_index
      (link_key,source_type,source_id,target_type,target_id,relation_type,relation_family,source_table,source_record_id,confidence,evidence_url,metadata)
      SELECT md5(concat_ws('|','pc_defence_programmes',j->>'defence_programme_id','customer',j->>'customer_entity_id')),
             'programme',j->>'defence_programme_id','entity',j->>'customer_entity_id',
             'customer','strategic_industry','pc_defence_programmes',j->>'defence_programme_id',
             j->>'verification_status',j->>'source_url',j
      FROM public.pc_defence_programmes t CROSS JOIN LATERAL to_jsonb(t) j
      WHERE nullif(j->>'customer_entity_id','') IS NOT NULL
      ON CONFLICT (link_key) DO NOTHING
    $q$;

    EXECUTE $q$
      INSERT INTO public.pc_terminal_link_index
      (link_key,source_type,source_id,target_type,target_id,relation_type,relation_family,source_table,source_record_id,confidence,evidence_url,metadata)
      SELECT md5(concat_ws('|','pc_defence_programmes',j->>'defence_programme_id','lead_contractor',j->>'lead_contractor_entity_id')),
             'programme',j->>'defence_programme_id','entity',j->>'lead_contractor_entity_id',
             'lead_contractor','strategic_industry','pc_defence_programmes',j->>'defence_programme_id',
             j->>'verification_status',j->>'source_url',j
      FROM public.pc_defence_programmes t CROSS JOIN LATERAL to_jsonb(t) j
      WHERE nullif(j->>'lead_contractor_entity_id','') IS NOT NULL
      ON CONFLICT (link_key) DO NOTHING
    $q$;
  END IF;

  IF to_regclass('public.pc_defence_programme_participants') IS NOT NULL THEN
    EXECUTE $q$
      INSERT INTO public.pc_terminal_link_index
      (link_key,source_type,source_id,target_type,target_id,relation_type,relation_family,source_table,source_record_id,confidence,evidence_url,metadata)
      SELECT md5(concat_ws('|','pc_defence_programme_participants',j->>'defence_programme_id',j->>'entity_id',j->>'participant_role')),
             'programme',j->>'defence_programme_id','entity',j->>'entity_id',
             coalesce(nullif(j->>'participant_role',''),'participant'),
             'strategic_industry','pc_defence_programme_participants',
             coalesce(j->>'programme_participant_id',j->>'id'),
             j->>'verification_status',j->>'source_url',j
      FROM public.pc_defence_programme_participants t CROSS JOIN LATERAL to_jsonb(t) j
      WHERE nullif(j->>'defence_programme_id','') IS NOT NULL AND nullif(j->>'entity_id','') IS NOT NULL
      ON CONFLICT (link_key) DO NOTHING
    $q$;

    EXECUTE $q$
      INSERT INTO public.pc_terminal_link_index
      (link_key,source_type,source_id,target_type,target_id,relation_type,relation_family,source_table,source_record_id,confidence,evidence_url,metadata)
      SELECT md5(concat_ws('|','pc_defence_programme_participants',j->>'defence_programme_id',j->>'shipyard_asset_id',j->>'participant_role')),
             'programme',j->>'defence_programme_id','asset',j->>'shipyard_asset_id',
             coalesce(nullif(j->>'participant_role',''),'shipyard'),
             'strategic_industry','pc_defence_programme_participants',
             coalesce(j->>'programme_participant_id',j->>'id'),
             j->>'verification_status',j->>'source_url',j
      FROM public.pc_defence_programme_participants t CROSS JOIN LATERAL to_jsonb(t) j
      WHERE nullif(j->>'defence_programme_id','') IS NOT NULL AND nullif(j->>'shipyard_asset_id','') IS NOT NULL
      ON CONFLICT (link_key) DO NOTHING
    $q$;
  END IF;

  IF to_regclass('public.pc_security_operation_participants') IS NOT NULL THEN
    EXECUTE $q$
      INSERT INTO public.pc_terminal_link_index
      (link_key,source_type,source_id,target_type,target_id,relation_type,relation_family,source_table,source_record_id,confidence,evidence_url,metadata)
      SELECT md5(concat_ws('|','pc_security_operation_participants',j->>'security_operation_id',coalesce(j->>'entity_id',j->>'mobile_asset_id'),j->>'participant_role')),
             'security_operation',j->>'security_operation_id',
             CASE WHEN nullif(j->>'mobile_asset_id','') IS NOT NULL THEN 'mobile_asset' ELSE 'entity' END,
             coalesce(nullif(j->>'mobile_asset_id',''),j->>'entity_id'),
             coalesce(nullif(j->>'participant_role',''),'participant'),
             'security_operation','pc_security_operation_participants',
             coalesce(j->>'security_operation_participant_id',j->>'id'),
             j->>'verification_status',j->>'source_url',j
      FROM public.pc_security_operation_participants t CROSS JOIN LATERAL to_jsonb(t) j
      WHERE nullif(j->>'security_operation_id','') IS NOT NULL
        AND coalesce(nullif(j->>'mobile_asset_id',''),nullif(j->>'entity_id','')) IS NOT NULL
      ON CONFLICT (link_key) DO NOTHING
    $q$;
  END IF;

  SELECT count(*) INTO object_count FROM public.pc_terminal_object_index;
  SELECT count(*) INTO link_count FROM public.pc_terminal_link_index;

  RETURN jsonb_build_object(
    'status','ok',
    'object_count',object_count,
    'link_count',link_count,
    'refreshed_at',now()
  );
END;
$$;

CREATE OR REPLACE FUNCTION public.pc_terminal_search(p_query text, p_limit integer DEFAULT 40)
RETURNS TABLE (
  object_type text,
  object_id text,
  display_name text,
  subtype text,
  country text,
  region text,
  status text,
  rank_score numeric
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path=public
AS $$
  WITH q AS (
    SELECT trim(coalesce(p_query,'')) AS term
  )
  SELECT
    o.object_type,o.object_id,o.display_name,o.subtype,o.country,o.region,o.status,
    (
      CASE WHEN lower(o.display_name)=lower(q.term) THEN 1000 ELSE 0 END +
      CASE WHEN lower(o.display_name) LIKE lower(q.term)||'%' THEN 500 ELSE 0 END +
      CASE WHEN lower(o.display_name) LIKE '%'||lower(q.term)||'%' THEN 250 ELSE 0 END +
      greatest(similarity(lower(o.display_name),lower(q.term))*100,0) +
      CASE WHEN lower(o.search_text) LIKE '%'||lower(q.term)||'%' THEN 50 ELSE 0 END
    )::numeric AS rank_score
  FROM public.pc_terminal_object_index o CROSS JOIN q
  WHERE q.term<>''
    AND (
      o.display_name ILIKE '%'||q.term||'%'
      OR o.search_text ILIKE '%'||q.term||'%'
      OR similarity(lower(o.display_name),lower(q.term))>0.20
    )
  ORDER BY rank_score DESC, o.display_name
  LIMIT greatest(1,least(coalesce(p_limit,40),200));
$$;

-- Service-role only: the public apps use the backend/service client.
ALTER TABLE public.pc_terminal_object_index ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pc_terminal_link_index ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.pc_terminal_object_index FROM PUBLIC;
REVOKE ALL ON public.pc_terminal_link_index FROM PUBLIC;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.pc_terminal_object_index TO service_role;
GRANT SELECT,INSERT,UPDATE,DELETE ON public.pc_terminal_link_index TO service_role;
GRANT SELECT ON public.pc_v_terminal_links TO service_role;
GRANT SELECT ON public.pc_v_terminal_event_context TO service_role;
GRANT SELECT ON public.pc_v_terminal_context_counts TO service_role;
GRANT EXECUTE ON FUNCTION public.pc_refresh_terminal_indexes() TO service_role;
GRANT EXECUTE ON FUNCTION public.pc_terminal_search(text,integer) TO service_role;

COMMIT;

-- Run once after migration:
SELECT public.pc_refresh_terminal_indexes();
