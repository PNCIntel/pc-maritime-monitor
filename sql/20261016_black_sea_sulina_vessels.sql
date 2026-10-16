-- P&C Black Sea Sulina casualty package | 16 Oct 2026
-- Idempotent, source-qualified; inspect audit at end. No current-threat rating inferred.
-- This writes directly to canonical tables, not the staging-loader queue.
BEGIN;
DO $$
DECLARE
 v_w text; v_y text; v_owner text; v_mgr text; v_eid text; v_imo text; v_company text;
 v_row jsonb; v_meta jsonb;
BEGIN
 IF to_regprocedure('public.pc_upsert_json(text,jsonb,text[])') IS NULL THEN
   RAISE EXCEPTION 'pc_upsert_json is required; no changes have been made';
 END IF;
 -- Match physical identity by IMO first, and stop on ambiguous duplicates.
 FOR v_imo IN SELECT unnest(ARRAY['8808707','9221803']) LOOP
   IF (SELECT count(*) FROM public.pc_mobile_assets WHERE imo::text=v_imo)>1 THEN
     RAISE EXCEPTION 'Duplicate canonical vessel IMO %, reconcile first',v_imo;
   END IF;
 END LOOP;
 SELECT mobile_asset_id::text INTO v_w FROM public.pc_mobile_assets WHERE imo::text='8808707' LIMIT 1;
 SELECT mobile_asset_id::text INTO v_y FROM public.pc_mobile_assets WHERE imo::text='9221803' LIMIT 1;
 v_w:=coalesce(v_w,'MOB_PC_IMO_8808707');v_y:=coalesce(v_y,'MOB_PC_IMO_9221803');
 PERFORM public.pc_upsert_json('pc_mobile_assets',jsonb_build_object(
  'mobile_asset_id',v_w,'name','WINE TRADER','asset_type','vessel','imo','8808707',
  'metadata',jsonb_build_object('pc_black_sea_20261016',jsonb_build_object(
   'type','chemical tanker','flag_at_incident','San Marino','built',1989,'dwt',6259,
   'registered_owner_reported','WATERFALLS CO LTD','commercial_manager_reported','WATERFALLS CO LTD',
   'ism_manager_reported','SICILSHIP SRL',
   'ownership_source','https://magicport.ai/vessels/tanker/wine-trader-mmsi-351482000',
   'ownership_observation_note','Commercial registry observation, not independently certified beneficial ownership'))),ARRAY['mobile_asset_id']);
 PERFORM public.pc_upsert_json('pc_mobile_assets',jsonb_build_object(
  'mobile_asset_id',v_y,'name','YARA J','asset_type','vessel','imo','9221803',
  'metadata',jsonb_build_object('pc_black_sea_20261016',jsonb_build_object(
   'type','chemical/oil products tanker','flag_at_incident','Comoros','built',2001,'dwt',10018,
   'registered_owner_reported','YARA SHIPPING CO INC','commercial_manager_reported','YARA SHIPPING CO INC',
   'ism_manager_reported','YARA SHIPPING CO INC',
   'manager_qualification','Registry providers differ over ISM identity and observation dates; review before creating ISM edge',
   'identity_history_reported',jsonb_build_array('ARBOL','LOGO','ALHEERA','LOKI','ST MAUD'),
   'ownership_source','https://magicport.ai/vessels/tanker/yara-j-mmsi-620800363'))),ARRAY['mobile_asset_id']);
 -- Create named legal entities only after exact-name duplicate check; preserve existing identities.
 FOR v_company IN SELECT unnest(ARRAY['WATERFALLS CO LTD','SICILSHIP SRL','YARA SHIPPING CO INC']) LOOP
   IF (SELECT count(*) FROM public.pc_entities WHERE lower(trim(name))=lower(v_company))>1 THEN
      RAISE EXCEPTION 'Ambiguous entity name %; reconcile before ingest',v_company;
   END IF;
   SELECT entity_id::text INTO v_owner FROM public.pc_entities WHERE lower(trim(name))=lower(v_company) LIMIT 1;
   v_owner:=coalesce(v_owner,'ENTITY_PC_'||upper(regexp_replace(v_company,'[^A-Za-z0-9]','','g')));
   IF NOT EXISTS (SELECT 1 FROM public.pc_entities WHERE entity_id::text=v_owner) THEN
      PERFORM public.pc_upsert_json('pc_entities',jsonb_build_object('entity_id',v_owner,'name',v_company,
       'metadata',jsonb_build_object('research_status','reported_registry_identity','source_note','Vessel ownership/management registry; beneficial ownership not established')),ARRAY['entity_id']);
   END IF;
   v_owner:=NULL;
 END LOOP;
 -- Events: 14 Oct YARA J (fire reported), 15 Oct WINE TRADER (fire and SAR).
 -- No strike point fabricated. Reporting of drone causation and Russian origin is qualified.
 PERFORM public.pc_upsert_json('pc_events',jsonb_build_object(
 'event_id','PC_BS_SULINA_YARA_J_FIRE_20261014','title','YARA J reports fire near Sulina; crew extinguishes blaze',
 'start_date','2026-10-14T00:00:00+00:00','event_type','maritime_security_incident',
 'description','Comoros-flagged chemical/oil products tanker YARA J (IMO 9221803) reported a fire while anchored near Sulina on 14 October. Its 17 crew reportedly extinguished the blaze without injury. The crew reported a suspected drone strike; Romanian authorities were investigating the cause. No definite attacker or verified strike coordinates assigned.',
 'verification_status','official_statement_reported','intelligence_relevance',1,'intelligence_visible',true,'trade_visible',false,
 'metadata',jsonb_build_object('situation_id','PC_SIT_BLACK_SEA_SULINA_VESSEL_FIRES_20261014_15',
 'intelligence_lens','security','event_date_qualification','Date-level report; precise incident time not established',
 'geographic_scope','Sulina approaches, Romanian Black Sea waters; no exact strike point',
 'reported_crew',17,'injury_status','all crew reported safe','causation_status','suspected drone strike; investigation ongoing',
 'canonical_mobile_asset_id',v_y,'canonical_vessel_imo','9221803',
 'source_urls',jsonb_build_array('https://www.euronews.ro/articole/nava-lovita-de-o-drona-in-apele-teritoriale-ale-romaniei-langa-sulina-echipajul-a','https://en.interfax.com.ua/news/general/1220668.html'),
 'source_claims',jsonb_build_array(
 jsonb_build_object('publisher','Euronews Romania / MRCC','published_at','2026-10-14','verification_status','reported_official','claim','MRCC reported tanker fire and rescue response; crew subsequently reported fire extinguished and persons safe.','original_url','https://www.euronews.ro/articole/nava-lovita-de-o-drona-in-apele-teritoriale-ale-romaniei-langa-sulina-echipajul-a'),
 jsonb_build_object('publisher','Interfax-Ukraine citing Romanian reports','published_at','2026-10-15','verification_status','reported','claim','Crew-reported suspected drone impact; 17 crew safe; causation not independently established.','original_url','https://en.interfax.com.ua/news/general/1220668.html')))),ARRAY['event_id']);
 PERFORM public.pc_upsert_json('pc_events',jsonb_build_object(
 'event_id','PC_BS_SULINA_WINE_TRADER_FIRE_20261015','title','WINE TRADER burns near Sulina; seven seafarers reported missing after revised rescue count',
 'start_date','2026-10-15T00:00:00+00:00','event_type','maritime_security_incident',
 'description','San Marino-flagged chemical tanker WINE TRADER (IMO 8808707) reported a fire near Sulina on 15 October with 12 aboard. Early reports said four rescued and eight missing; later Romanian Naval Authority reporting said five rescued and seven missing. Search and rescue continued at publication. The cause and strike attribution remain under investigation; no precise ship-fire coordinates inferred.',
 'verification_status','official_statement_reported','intelligence_relevance',1,'intelligence_visible',true,'trade_visible',false,
 'metadata',jsonb_build_object('situation_id','PC_SIT_BLACK_SEA_SULINA_VESSEL_FIRES_20261014_15',
 'intelligence_lens','security','geographic_scope','Approximately 13 nautical miles southeast of Sulina, Romania; area-level reference, not plotted strike point',
 'canonical_mobile_asset_id',v_w,'canonical_vessel_imo','8808707',
 'casualty_reporting_history',jsonb_build_array(
 jsonb_build_object('stage','initial','rescued',4,'missing',8,'source','early Reuters / Romanian reports'),
 jsonb_build_object('stage','revised','rescued',5,'missing',7,'source','Romanian Naval Authority later reporting via Reuters and AP')),
 'causation_status','fire confirmed; drone attack and perpetrator under investigation',
 'source_urls',jsonb_build_array('https://www.reuters.com/world/two-ships-ablaze-romanian-black-sea-waters-8-sailors-missing-2026-10-15/','https://www.euronews.com/2026/10/15/romania-probes-possible-drone-attack-on-tanker-in-its-black-sea-territorial-waters'),
 'source_claims',jsonb_build_array(
 jsonb_build_object('publisher','Reuters','published_at','2026-10-15','verification_status','reported_official','claim','Later account reports five rescued and seven missing; earlier report had four rescued and eight missing.','original_url','https://www.reuters.com/world/two-ships-ablaze-romanian-black-sea-waters-8-sailors-missing-2026-10-15/'),
 jsonb_build_object('publisher','Euronews citing Romanian Naval Authority','published_at','2026-10-15','verification_status','reported_official','claim','Fire and SAR near Sulina; Romanian authorities did not initially establish whether a drone caused the fire.','original_url','https://www.euronews.com/2026/10/15/romania-probes-possible-drone-attack-on-tanker-in-its-black-sea-territorial-waters')))),ARRAY['event_id']);
 -- Direct graph attachment by resolved physical identity, never an ownership allegation.
 PERFORM public.pc_upsert_json('pc_event_links',jsonb_build_object(
  'event_link_id','EVLINK_PC_BS_YARA_J_20261014','event_id','PC_BS_SULINA_YARA_J_FIRE_20261014',
  'linked_type','mobile_asset','linked_id',v_y,'linked_name','YARA J','relationship','vessel involved',
  'metadata',jsonb_build_object('identity_basis','IMO 9221803')),ARRAY['event_link_id']);
 PERFORM public.pc_upsert_json('pc_event_links',jsonb_build_object(
  'event_link_id','EVLINK_PC_BS_WINE_TRADER_20261015','event_id','PC_BS_SULINA_WINE_TRADER_FIRE_20261015',
  'linked_type','mobile_asset','linked_id',v_w,'linked_name','WINE TRADER','relationship','vessel involved',
  'metadata',jsonb_build_object('identity_basis','IMO 8808707')),ARRAY['event_link_id']);
 -- Source-qualified cross-event relation stays contextual; no shared perpetrator inferred.
 UPDATE public.pc_events SET metadata=coalesce(metadata,'{}'::jsonb)||
 jsonb_build_object('curated_related_events',jsonb_build_array(
  jsonb_build_object('event_id','PC_BS_SULINA_YARA_J_FIRE_20261014','relationship','Near-contemporaneous regional casualty','rationale','Separate tanker fire around Sulina; common actor/cause not established')))
 WHERE event_id='PC_BS_SULINA_WINE_TRADER_FIRE_20261015';
END $$;
COMMIT;
SELECT e.event_id,e.title,e.start_date,e.verification_status,e.intelligence_visible,
 m.name vessel,m.imo,m.metadata->'pc_black_sea_20261016' vessel_research
FROM public.pc_events e LEFT JOIN public.pc_event_links l ON l.event_id=e.event_id AND l.linked_type='mobile_asset'
LEFT JOIN public.pc_mobile_assets m ON m.mobile_asset_id::text=l.linked_id::text
WHERE e.event_id IN ('PC_BS_SULINA_YARA_J_FIRE_20261014','PC_BS_SULINA_WINE_TRADER_FIRE_20261015')
ORDER BY e.start_date;
