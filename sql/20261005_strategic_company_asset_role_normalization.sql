-- P&C strategic industry normalization: safe structural backfill
-- 2026-10-05
-- Purpose: mirror already-canonical asset owner/operator facts into pc_company_asset_roles.
-- This DOES NOT infer ownership, merge entities, create programmes/contracts, or alter historical relationships.
-- It only acts where pc_assets already names the entity and a source_id is present.

BEGIN;

-- Prevent concurrent cleanup runs.
SELECT pg_advisory_xact_lock(hashtext('pc_strategic_company_asset_role_normalization_v1'));

-- Preflight: these are the exact candidate facts that will be mirrored.
CREATE TEMP TABLE _pc_strategic_role_candidates ON COMMIT DROP AS
SELECT DISTINCT
    a.asset_id,
    a.operator_entity_id AS entity_id,
    'operator'::text AS asset_role,
    a.source_id
FROM public.pc_assets a
WHERE a.operator_entity_id IS NOT NULL
  AND a.source_id IS NOT NULL
  AND (
       lower(coalesce(a.asset_type,'')) LIKE '%shipyard%'
    OR lower(coalesce(a.subtype,'')) LIKE '%shipyard%'
    OR EXISTS (SELECT 1 FROM public.pc_shipyard_details sd WHERE sd.asset_id=a.asset_id)
  )
UNION
SELECT DISTINCT
    a.asset_id,
    a.owner_entity_id AS entity_id,
    'owner'::text AS asset_role,
    a.source_id
FROM public.pc_assets a
WHERE a.owner_entity_id IS NOT NULL
  AND a.source_id IS NOT NULL
  AND (
       lower(coalesce(a.asset_type,'')) LIKE '%shipyard%'
    OR lower(coalesce(a.subtype,'')) LIKE '%shipyard%'
    OR EXISTS (SELECT 1 FROM public.pc_shipyard_details sd WHERE sd.asset_id=a.asset_id)
  );

DO $$
DECLARE bad_count integer;
BEGIN
  SELECT count(*) INTO bad_count
  FROM _pc_strategic_role_candidates c
  LEFT JOIN public.pc_entities e ON e.entity_id=c.entity_id
  LEFT JOIN public.pc_assets a ON a.asset_id=c.asset_id
  LEFT JOIN public.pc_sources s ON s.source_id=c.source_id
  WHERE e.entity_id IS NULL OR a.asset_id IS NULL OR s.source_id IS NULL;

  IF bad_count > 0 THEN
    RAISE EXCEPTION 'Strategic role normalization aborted: % candidate(s) fail entity/asset/source integrity.', bad_count;
  END IF;
END $$;

-- Use deterministic IDs; avoid ON CONFLICT assumptions about table-specific constraints.
INSERT INTO public.pc_company_asset_roles (
    company_asset_role_id,
    entity_id,
    asset_id,
    mobile_asset_id,
    asset_role,
    role_status,
    valid_from,
    valid_to,
    as_of,
    source_id,
    research_claim_id,
    metadata
)
SELECT
    'CAR_STRAT_' || upper(substr(md5(c.entity_id || '|' || c.asset_id || '|' || c.asset_role),1,24)),
    c.entity_id,
    c.asset_id,
    NULL,
    c.asset_role,
    'active',
    NULL,
    NULL,
    CURRENT_DATE,
    c.source_id,
    NULL,
    jsonb_build_object(
        'normalization','pc_assets canonical owner/operator mirror',
        'normalization_version','2026-10-05-v1',
        'inference',false
    )
FROM _pc_strategic_role_candidates c
WHERE NOT EXISTS (
    SELECT 1
    FROM public.pc_company_asset_roles r
    WHERE r.entity_id=c.entity_id
      AND r.asset_id=c.asset_id
      AND lower(coalesce(r.asset_role,''))=c.asset_role
      AND r.valid_to IS NULL
);

COMMIT;

-- Validation: expected example is Damen Shiprepair Rotterdam becoming an active operator role.
SELECT
    e.name AS entity_name,
    a.name AS asset_name,
    r.asset_role,
    r.role_status,
    r.source_id,
    r.metadata
FROM public.pc_company_asset_roles r
JOIN public.pc_entities e ON e.entity_id=r.entity_id
JOIN public.pc_assets a ON a.asset_id=r.asset_id
WHERE r.metadata->>'normalization_version'='2026-10-05-v1'
ORDER BY e.name,a.name,r.asset_role;

-- Remaining shipyard normalization gaps. These require review rather than inference.
SELECT *
FROM public.pc_v_strategic_facility_audit
WHERE graph_status <> 'CONNECTED_OR_CONTEXTUAL'
ORDER BY country,name;
