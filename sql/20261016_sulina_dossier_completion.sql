-- P&C Sulina dossier completion, 16 October 2026
-- Requires successful V5 and graph/evidence repair (4 edges, 4 evidence).
-- Editorially qualified: 'Not assessed' is not a low-risk score. No attributed attacker.
BEGIN;
DO $$
DECLARE r record; w text; y text; water text; sicil text; yara text; evidence_n int; edge_n int; rel_def text; role text; rel_id bigint;
BEGIN
 SELECT mobile_asset_id INTO STRICT w FROM public.pc_mobile_assets WHERE imo='8808707';
 SELECT mobile_asset_id INTO STRICT y FROM public.pc_mobile_assets WHERE imo='9221803';
 SELECT entity_id INTO STRICT water FROM public.pc_entities WHERE lower(trim(name))='waterfalls co ltd';
 SELECT entity_id INTO STRICT sicil FROM public.pc_entities WHERE lower(trim(name))='sicilship srl';
 SELECT entity_id INTO STRICT yara FROM public.pc_entities WHERE lower(trim(name))='yara shipping co inc';
 SELECT count(*) INTO evidence_n FROM public.pc_event_evidence
 WHERE event_id IN ('PC_BS_SULINA_YARA_J_FIRE_20261014','PC_BS_SULINA_WINE_TRADER_FIRE_20261015');
 SELECT count(*) INTO edge_n FROM public.pc_relationships WHERE relationship_id LIKE 'REL_PC_BS_20261016_%';
 IF evidence_n < 4 OR edge_n < 4 THEN RAISE EXCEPTION 'Missing prior evidence/graph repair: evidence %, edges %',evidence_n,edge_n; END IF;
 -- Promote sourced vessel attributes to their structured columns without replacing pre-existing canonical data.
 UPDATE public.pc_mobile_assets SET
 subtype=coalesce(subtype,'chemical tanker'),flag=coalesce(flag,'San Marino'),
 year_built=coalesce(year_built,1989),dwt=coalesce(dwt,6259),
 owner_entity_id=coalesce(owner_entity_id,water),
 manager_entity_id=coalesce(manager_entity_id,sicil)
 WHERE mobile_asset_id=w;
 UPDATE public.pc_mobile_assets SET
 subtype=coalesce(subtype,'chemical/oil products tanker'),flag=coalesce(flag,'Comoros'),
 year_built=coalesce(year_built,2001),dwt=coalesce(dwt,10018),
 owner_entity_id=coalesce(owner_entity_id,yara)
 WHERE mobile_asset_id=y;
 -- No YARA J ISM manager FK assigned: the registry observations conflict.
 -- Link involved entities to actual incident, with role-qualification carried in graph metadata.
 FOR r IN SELECT * FROM (VALUES
 ('PC_BS_SULINA_WINE_TRADER_FIRE_20261015',water,'WATERFALLS CO LTD','reported registered owner',w),
 ('PC_BS_SULINA_WINE_TRADER_FIRE_20261015',sicil,'SICILSHIP SRL','reported ISM manager',w),
 ('PC_BS_SULINA_YARA_J_FIRE_20261014',yara,'YARA SHIPPING CO INC','reported registered owner / commercial manager',y)
 ) t(event_id,entity_id,entity_name,role,vessel_id)
 LOOP
 INSERT INTO public.pc_event_links(event_link_id,event_id,linked_type,linked_id,linked_name,relationship,confidence,metadata)
 VALUES ('EVLINK_PC_BS_ENT_'||upper(md5(r.event_id||'|'||r.entity_id)),r.event_id,'entity',r.entity_id,r.entity_name,r.role,'medium',
 jsonb_build_object('observation_date','2026-10-16','relationship_basis','Commercial registry, source qualified','vessel_id',r.vessel_id,'beneficial_ownership','not established'))
 ON CONFLICT (event_link_id) DO UPDATE SET metadata=coalesce(pc_event_links.metadata,'{}'::jsonb)||EXCLUDED.metadata;
 END LOOP;
 -- Materialize a shared regional event link for the connected-event reader, explicitly noncausal.
 INSERT INTO public.pc_event_links(event_link_id,event_id,linked_type,linked_id,linked_name,relationship,confidence,metadata)
 VALUES('EVLINK_PC_BS_WINE_YARA_CONTEXT','PC_BS_SULINA_WINE_TRADER_FIRE_20261015','event',
 'PC_BS_SULINA_YARA_J_FIRE_20261014','YARA J fire near Sulina','related regional development','medium',
 jsonb_build_object('common_actor','not established','common_cause','not established','situation_id','PC_SIT_BLACK_SEA_SULINA_VESSEL_FIRES_20261014_15'))
 ON CONFLICT (event_link_id) DO UPDATE SET metadata=coalesce(pc_event_links.metadata,'{}'::jsonb)||EXCLUDED.metadata;
 -- Editorial profiles based on source evidence, no claim of independent forensics.
 FOR r IN SELECT event_id FROM public.pc_events WHERE event_id IN
 ('PC_BS_SULINA_YARA_J_FIRE_20261014','PC_BS_SULINA_WINE_TRADER_FIRE_20261015')
 LOOP
 UPDATE public.pc_events e SET metadata=coalesce(e.metadata,'{}'::jsonb)||jsonb_build_object(
 'editorial_profile',jsonb_build_object(
 'review_status','approved','approval_basis','P&C completion requested 16 October 2026; source-qualified editorial publication, not an independent incident investigation',
 'significance','major','current_threat','not_assessed',
 'current_threat_label','Not assessed — continuing vessel or corridor-specific threat has not been established',
 'assessed_at',to_char(current_timestamp AT TIME ZONE 'Asia/Dubai','YYYY-MM-DD"T"HH24:MI:SS')||'+04:00',
 'evidence_confidence','Moderate — vessel fires and rescue situation reported; suspected strike mechanism and attribution unconfirmed',
 'significance_rationale','Separate tanker fire reports near the Sulina approaches and a search-and-rescue emergency warrant scrutiny of Black Sea–Danube access. They do not establish a common attacker, a port closure, cargo interruption or an ongoing vessel-specific threat.',
 'analysis',CASE WHEN e.event_id='PC_BS_SULINA_YARA_J_FIRE_20261014' THEN
 'YARA J (IMO 9221803), flagged Comoros in reporting, experienced a fire near Sulina; its 17 crew were reported safe after the blaze was extinguished. A suspected drone strike was reported, but cause and attribution remain unconfirmed. Yara Shipping Co Inc is a reported registered owner and commercial manager; its ISM identity requires registry reconciliation. No confirmed terminal outage or spill is established in the cited reports.'
 ELSE
 'WINE TRADER (IMO 8808707), flagged San Marino in reporting, caught fire near Sulina with 12 aboard. Initial counts of four rescued and eight missing were revised to five rescued and seven missing. Search-and-rescue status requires fresh confirmation. Waterfalls Co Ltd is registry-reported registered owner and Sicilship SRL reported ISM manager, not verified beneficial ownership. Any pollution, navigation restriction or confirmed strike cause requires official corroboration.'
 END,
 'outlook','Monitor Romanian naval/MRCC updates, forensic findings, navigational notices and pollution response. The proximity of the two casualties is not proof of a coordinated operation. Reassess if official notices establish a Sulina navigation restriction, additional casualties, an environmental release or verified new merchant-vessel attacks.',
 'monitoring',jsonb_build_array(
 'Romanian Naval Authority/MRCC: updated rescue totals and dispositions, especially WINE TRADER.',
 'Official forensic or security findings: cause and attribution for each vessel, separately.',
 'Danube/Sulina traffic and pilotage notices: any verified restrictions or navigation hazards.',
 'Environmental agencies and port notices: confirmed cargo/bunker release or cleanup activation.',
 'Registry reconciliation: dated owner, commercial and ISM/technical manager extracts by IMO.',
 'Any separately corroborated merchant shipping casualties nearby; do not conflate distinct incidents.'
 ),
 'source_urls',coalesce(e.metadata->'source_urls','[]'::jsonb),
 'report_date_qualification','Day-level casualty dates. Assessment timestamp records editorial preparation/publication on 16 Oct, not the original incident clock time.'
 ))
 WHERE e.event_id=r.event_id;
 END LOOP;
END $$;
COMMIT;
SELECT e.event_id,e.metadata->'editorial_profile'->>'review_status' editorial_status,
e.metadata->'editorial_profile'->>'current_threat_label' current_risk,
e.metadata->'editorial_profile'->>'evidence_confidence' confidence,
e.metadata->'editorial_profile'->>'assessed_at' assessed_at,
(SELECT count(*) FROM public.pc_event_evidence v WHERE v.event_id=e.event_id) evidence_records,
(SELECT count(*) FROM public.pc_event_links l WHERE l.event_id=e.event_id) event_links
FROM public.pc_events e
WHERE e.event_id IN ('PC_BS_SULINA_YARA_J_FIRE_20261014','PC_BS_SULINA_WINE_TRADER_FIRE_20261015')
ORDER BY e.start_date;
