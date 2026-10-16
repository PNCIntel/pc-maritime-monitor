-- Sulina graph/evidence repair | 16 October 2026 | source-qualified, provisional
-- Run AFTER v5 ingestion. No automatic editorial approval or inferred beneficial ownership.
BEGIN;
DO $$
DECLARE w text; y text; water text; sicil text; yara text; n int; r record; edge_id text; ev_id bigint;
BEGIN
 SELECT mobile_asset_id INTO STRICT w FROM public.pc_mobile_assets WHERE imo='8808707';
 SELECT mobile_asset_id INTO STRICT y FROM public.pc_mobile_assets WHERE imo='9221803';
 SELECT entity_id INTO STRICT water FROM public.pc_entities WHERE lower(trim(name))='waterfalls co ltd';
 SELECT entity_id INTO STRICT sicil FROM public.pc_entities WHERE lower(trim(name))='sicilship srl';
 SELECT entity_id INTO STRICT yara FROM public.pc_entities WHERE lower(trim(name))='yara shipping co inc';
 IF NOT EXISTS(SELECT 1 FROM public.pc_event_links WHERE event_id='PC_BS_SULINA_WINE_TRADER_FIRE_20261015' AND linked_type='mobile_asset' AND linked_id=w)
 OR NOT EXISTS(SELECT 1 FROM public.pc_event_links WHERE event_id='PC_BS_SULINA_YARA_J_FIRE_20261014' AND linked_type='mobile_asset' AND linked_id=y)
 THEN RAISE EXCEPTION 'Canonical vessel-to-event links missing. Stop.'; END IF;
 -- Reported registered ownership is NOT ultimate beneficial ownership. Dates are observation dates, not inception of role.
 FOR r IN SELECT * FROM (VALUES
 (water,w,'registered_owner_reported','WINE TRADER','https://magicport.ai/vessels/tanker/wine-trader-mmsi-351482000','Registry-reported registered owner; ultimate beneficial ownership unverified'),
 (sicil,w,'ism_manager_reported','WINE TRADER','https://magicport.ai/vessels/tanker/wine-trader-mmsi-351482000','Registry-reported ISM manager; reconfirm with dated registry extract'),
 (yara,y,'registered_owner_reported','YARA J','https://magicport.ai/vessels/tanker/yara-j-mmsi-620800363','Registry-reported registered owner; ultimate beneficial ownership unverified'),
 (yara,y,'commercial_manager_reported','YARA J','https://magicport.ai/vessels/tanker/yara-j-mmsi-620800363','Commercial manager reported; conflicting ISM management accounts left unresolved')
 ) AS x(company_id,vessel_id,role,vessel_name,url,qualifier)
 LOOP
 edge_id:='REL_PC_BS_20261016_'||upper(md5(r.company_id||'|'||r.vessel_id||'|'||r.role));
 INSERT INTO public.pc_relationships
 (relationship_id,source_type,source_id,relationship_type,target_type,target_id,confidence,record_status,notes,metadata)
 VALUES (edge_id,'entity',r.company_id,r.role,'mobile_asset',r.vessel_id,'medium','provisional',r.qualifier,
 jsonb_build_object('source_urls',jsonb_build_array(r.url),'observed_on','2026-10-16','date_qualification','Registry observation, not role start date','vessel_name',r.vessel_name,'identity_basis','IMO-based canonical match','editorial_status','requires_registry_review'))
 ON CONFLICT (relationship_id) DO UPDATE SET
 notes=EXCLUDED.notes,metadata=coalesce(pc_relationships.metadata,'{}'::jsonb)||EXCLUDED.metadata;
 END LOOP;
 -- Real evidence records. Stable negative bigint identifiers (with collision guard).
 FOR r IN
 SELECT e.event_id,claim->>'claim' claim,claim->>'publisher' publisher,
 claim->>'original_url' url,claim->>'verification_status' status,
 claim->>'published_at' published, row_number() over (partition by e.event_id order by claim->>'original_url') seq
 FROM public.pc_events e CROSS JOIN LATERAL jsonb_array_elements(coalesce(e.metadata->'source_claims','[]'::jsonb)) claim
 WHERE e.event_id IN ('PC_BS_SULINA_YARA_J_FIRE_20261014','PC_BS_SULINA_WINE_TRADER_FIRE_20261015')
 LOOP
 ev_id:=-(abs(hashtext('PC_BS_EVIDENCE|'||r.event_id||'|'||coalesce(r.url,'')||'|'||r.seq)::bigint)+100000000);
 IF EXISTS(SELECT 1 FROM public.pc_event_evidence WHERE evidence_id=ev_id AND (event_id<>r.event_id OR original_url IS DISTINCT FROM r.url))
 THEN RAISE EXCEPTION 'Evidence identifier collision %',ev_id; END IF;
 INSERT INTO public.pc_event_evidence
 (evidence_id,event_id,claim,document_title,original_url,published_at,verification_status,observation_type,precision_note,metadata)
 VALUES (ev_id,r.event_id,r.claim,r.publisher,r.url,
 CASE WHEN r.published ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' THEN (r.published||' 00:00:00+00')::timestamptz ELSE NULL END,
 coalesce(r.status,'reported'),'assertion',
 'Publication date, not verified incident time; attribution and casualty figures are source-qualified',
 jsonb_build_object('intake','20261016_sulina','publication_date_precision','day','source_qualifier','Claim attributed to reporting; not independent validation'))
 ON CONFLICT (evidence_id) DO UPDATE SET claim=EXCLUDED.claim,metadata=coalesce(pc_event_evidence.metadata,'{}'::jsonb)||EXCLUDED.metadata;
 END LOOP;
 -- Explicit event-to-event link; NOT a common-perpetrator claim. Existing IDs protected.
 ev_id:=-(abs(hashtext('PC_BS_SULINA_YARA_J_FIRE_20261014|PC_BS_SULINA_WINE_TRADER_FIRE_20261015|regional_context')::bigint)+100000000);
 IF EXISTS(SELECT 1 FROM public.pc_event_relationships WHERE relationship_id=ev_id AND
 (from_event_id<>'PC_BS_SULINA_YARA_J_FIRE_20261014' OR to_event_id<>'PC_BS_SULINA_WINE_TRADER_FIRE_20261015'))
 THEN RAISE EXCEPTION 'Event relationship ID collision %',ev_id; END IF;
 INSERT INTO public.pc_event_relationships
 (relationship_id,from_event_id,to_event_id,relationship_type,claim_status,rationale,metadata)
 VALUES (ev_id,'PC_BS_SULINA_YARA_J_FIRE_20261014','PC_BS_SULINA_WINE_TRADER_FIRE_20261015',
 'shared_regional_context','reported',
 'Separate tanker-fire reports near Sulina on successive dates; shared location does not establish a common cause or perpetrator.',
 jsonb_build_object('situation_id','PC_SIT_BLACK_SEA_SULINA_VESSEL_FIRES_20261014_15','review_date','2026-10-16','causal_link','not_established'))
 ON CONFLICT (relationship_id) DO UPDATE SET rationale=EXCLUDED.rationale,metadata=coalesce(pc_event_relationships.metadata,'{}'::jsonb)||EXCLUDED.metadata;
END $$;
COMMIT;
SELECT 'corporate_edges' section,count(*) n FROM public.pc_relationships WHERE relationship_id LIKE 'REL_PC_BS_20261016_%'
UNION ALL SELECT 'evidence_records',count(*) FROM public.pc_event_evidence WHERE event_id IN ('PC_BS_SULINA_YARA_J_FIRE_20261014','PC_BS_SULINA_WINE_TRADER_FIRE_20261015')
UNION ALL SELECT 'event_relationships',count(*) FROM public.pc_event_relationships WHERE from_event_id='PC_BS_SULINA_YARA_J_FIRE_20261014' AND to_event_id='PC_BS_SULINA_WINE_TRADER_FIRE_20261015';
