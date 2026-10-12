-- Power & Corridors | CLI Brazil infrastructure completion | 2026-10-12
-- One transaction, rerunnable. Preserves existing terminal identities, ownership and geometry.
-- TEGRAM shared assets are NOT represented as exclusively owned/operated by CLI Norte.
-- Sources: https://tegramsite.azurewebsites.net/sobre/
-- https://www.portodoitaqui.com.br/public/porto-do-itaqui/planejamento-desenvolvimento/projetos-correntes
-- https://tegramsite.azurewebsites.net/projeto-da-3a-fase-de-expansao-do-tegram-e-aprovado-pelo-ministerio-de-portos-e-aeroportos/
BEGIN;
DO $cli$
DECLARE
 v_complex text; v_rail text; v_berth text; v_code text;
 v_source text := 'https://tegramsite.azurewebsites.net/sobre/';
 v_port_source text := 'https://www.portodoitaqui.com.br/public/porto-do-itaqui/planejamento-desenvolvimento/projetos-correntes';
BEGIN
 IF NOT EXISTS (SELECT 1 FROM public.pc_terminal_details WHERE asset_id='ASSET_V125_004' AND operator_entity_id='COMP_CLI_NORTE' AND parent_port_asset_id='PORTV1251_ITAQUI')
 OR NOT EXISTS (SELECT 1 FROM public.pc_terminal_details WHERE asset_id='ASSET_E474094DC4F76BBFEBF5' AND operator_entity_id='COMP_CLI_SUL' AND parent_port_asset_id='PORTG0049') THEN
  RAISE EXCEPTION 'Existing CLI operator/port reconciliation is missing or changed. No modifications made.';
 END IF;
 -- Reuse a pre-existing explicit TEGRAM terminal where unique; otherwise create the shared complex.
 SELECT asset_id INTO v_complex FROM public.pc_assets
 WHERE country ILIKE 'Brazil%' AND (name ILIKE 'TEGRAM%' OR name ILIKE 'Terminal de Grãos do Maranhão%')
 AND asset_type ILIKE '%terminal%' ORDER BY CASE WHEN asset_id='TERM_BR_ITAQUI_TEGRAM_SHARED' THEN 0 ELSE 1 END, asset_id LIMIT 1;
 IF v_complex IS NULL THEN
   v_complex := 'TERM_BR_ITAQUI_TEGRAM_SHARED';
   INSERT INTO public.pc_assets (asset_id,name,asset_type,country,region_city,record_status,metadata)
   VALUES (v_complex,'TEGRAM - Terminal de Grãos do Maranhão','terminal','Brazil','São Luís, Maranhão','verified',
     jsonb_build_object('shared_complex',true,'four_operator_lots',true,'source_url',v_source,'role_note','Shared TEGRAM complex; CLI is operator of Lot 3 only'))
   ON CONFLICT (asset_id) DO NOTHING;
 END IF;
 INSERT INTO public.pc_terminal_details (asset_id,parent_port_asset_id,terminal_type,berth_count,capacity,equipment,metadata,last_verified)
 VALUES(v_complex,'PORTV1251_ITAQUI','agri_bulk',2,
  jsonb_build_object('static_storage_tonnes_shared_complex',500000,'warehouses',4,'storage_tonnes_per_warehouse',125000,'annual_handling_tonnes_reported_greater_than',15000000,'annual_capacity_source_period','TEGRAM 2024 release'),
  jsonb_build_object('shared_rail_reception',true,'shared_maritime_loading',true,'individual_road_reception_per_lot',true),
  jsonb_build_object('shared_assets_not_exclusive_to_cli',true,'operating_lots',4,'source_urls',jsonb_build_array(v_source,v_port_source,'https://tegramsite.azurewebsites.net/projeto-da-3a-fase-de-expansao-do-tegram-e-aprovado-pelo-ministerio-de-portos-e-aeroportos/')),
  DATE '2026-10-12')
 ON CONFLICT(asset_id) DO UPDATE SET
  parent_port_asset_id=COALESCE(pc_terminal_details.parent_port_asset_id,EXCLUDED.parent_port_asset_id),
  berth_count=COALESCE(pc_terminal_details.berth_count,EXCLUDED.berth_count),
  capacity=COALESCE(pc_terminal_details.capacity,'{}'::jsonb)||EXCLUDED.capacity,
  equipment=COALESCE(pc_terminal_details.equipment,'{}'::jsonb)||EXCLUDED.equipment,
  metadata=COALESCE(pc_terminal_details.metadata,'{}'::jsonb)||EXCLUDED.metadata,
  last_verified=EXCLUDED.last_verified;
 -- CLI Norte's Lot 3 storage belongs to its lot, whereas berths 100 and 103 are TEGRAM-shared.
 UPDATE public.pc_terminal_details SET
  capacity=COALESCE(capacity,'{}'::jsonb)||jsonb_build_object('lot_static_storage_tonnes',125000,'capacity_scope','CLI Lot 3 only; not TEGRAM-wide throughput'),
  equipment=COALESCE(equipment,'{}'::jsonb)||jsonb_build_object('road_reception','lot-specific','shared_rail_reception',true,'shared_marine_loading',true),
  metadata=COALESCE(metadata,'{}'::jsonb)||jsonb_build_object('tegram_shared_terminal_asset_id',v_complex,'lot','3','berths_exclusive_to_cli',false,'source_url',v_source),last_verified=DATE '2026-10-12'
 WHERE asset_id='ASSET_V125_004';
 UPDATE public.pc_assets SET metadata=COALESCE(metadata,'{}'::jsonb)||jsonb_build_object('tegram_shared_terminal_asset_id',v_complex,'tegram_lot','3','evidence_url',v_source),updated_at=now()
 WHERE asset_id='ASSET_V125_004';
 -- Document real shared berths. Do not put the same berths beneath CLI's exclusive lot.
 FOREACH v_code IN ARRAY ARRAY['100','103'] LOOP
  SELECT b.asset_id INTO v_berth FROM public.pc_berth_details b JOIN public.pc_assets a ON a.asset_id=b.asset_id
  WHERE b.berth_code=v_code AND (b.terminal_asset_id=v_complex OR (a.name ILIKE '%Itaqui%' AND a.name ILIKE '%berth%'))
  ORDER BY CASE WHEN b.terminal_asset_id=v_complex THEN 0 ELSE 1 END,b.asset_id LIMIT 1;
  IF v_berth IS NULL THEN
    v_berth:='BERTH_BR_ITAQUI_TEGRAM_'||v_code;
    INSERT INTO public.pc_assets(asset_id,name,asset_type,country,region_city,record_status,metadata)
    VALUES(v_berth,'Itaqui TEGRAM shared berth '||v_code,'berth','Brazil','São Luís, Maranhão','verified',
      jsonb_build_object('shared_tegram_berth',true,'not_exclusive_to_cli',true,'source_url',v_port_source))
    ON CONFLICT(asset_id) DO NOTHING;
  END IF;
  INSERT INTO public.pc_berth_details(asset_id,terminal_asset_id,berth_code,berth_type,metadata)
  VALUES(v_berth,v_complex,v_code,'agri_bulk',jsonb_build_object('shared_by_tegram',true,'not_cli_exclusive',true,'source_url',v_port_source,'published_project_depth_m',15,'depth_note','Published project specification; not a current hydrographic survey'))
  ON CONFLICT(asset_id) DO UPDATE SET
    terminal_asset_id=COALESCE(pc_berth_details.terminal_asset_id,EXCLUDED.terminal_asset_id),
    metadata=COALESCE(pc_berth_details.metadata,'{}'::jsonb)||EXCLUDED.metadata;
 END LOOP;
 -- Shared rail reception is an interface, NOT a newly invented CN/VLI network segment.
 SELECT n.asset_id INTO v_rail FROM public.pc_rail_nodes n JOIN public.pc_assets a ON a.asset_id=n.asset_id
 WHERE a.country ILIKE 'Brazil%' AND (a.name ILIKE '%TEGRAM%rail%' OR n.asset_id='RAILNODE_BR_ITAQUI_TEGRAM_SHARED')
 ORDER BY CASE WHEN n.asset_id='RAILNODE_BR_ITAQUI_TEGRAM_SHARED' THEN 0 ELSE 1 END,n.asset_id LIMIT 1;
 IF v_rail IS NULL THEN
  v_rail:='RAILNODE_BR_ITAQUI_TEGRAM_SHARED';
  INSERT INTO public.pc_assets(asset_id,name,asset_type,country,region_city,record_status,metadata)
  VALUES(v_rail,'TEGRAM shared railway reception interface','rail_node','Brazil','São Luís, Maranhão','verified',
    jsonb_build_object('tegram_terminal_asset_id',v_complex,'source_url',v_port_source,'geometry_pending',true))
  ON CONFLICT(asset_id) DO NOTHING;
 END IF;
 INSERT INTO public.pc_rail_nodes(asset_id,node_type,port_connected,intermodal,metadata,last_verified)
 VALUES(v_rail,'port_rail_interface',true,true,jsonb_build_object('connected_terminal_asset_id',v_complex,'cli_lot_access','shared consortium interface','source_url',v_port_source,'network_and_operator_not_inferred',true),DATE '2026-10-12')
 ON CONFLICT(asset_id) DO UPDATE SET metadata=COALESCE(pc_rail_nodes.metadata,'{}'::jsonb)||EXCLUDED.metadata,last_verified=EXCLUDED.last_verified;
 UPDATE public.pc_terminal_details SET
   metadata=COALESCE(metadata,'{}'::jsonb)||jsonb_build_object('shared_rail_node_asset_id',v_rail,'shared_by_tegram',true)
 WHERE asset_id=v_complex;
 -- The other imported terminal candidates remain untouched; annotate ONLY known selected survivors.
 UPDATE public.pc_assets SET metadata=COALESCE(metadata,'{}'::jsonb)||jsonb_build_object('cli_identity_reconciliation',jsonb_build_object('preferred_existing_record',true,'other_candidate','ASSET_10C0070D509EDB385229','merge_status','pending_reference_audit')),updated_at=now()
 WHERE asset_id='ASSET_V125_004';
 UPDATE public.pc_assets SET metadata=COALESCE(metadata,'{}'::jsonb)||jsonb_build_object('cli_identity_reconciliation',jsonb_build_object('preferred_existing_record',true,'other_candidate','ASSET_V125_005','merge_status','pending_reference_audit','santos_berths','unverified_do_not_infer')),updated_at=now()
 WHERE asset_id='ASSET_E474094DC4F76BBFEBF5';
 RAISE NOTICE 'CLI shared TEGRAM terminal %, rail interface %; selected records updated. No ownership/geometry inferred.',v_complex,v_rail;
END $cli$;
COMMIT;
-- One result set: terminal/port graph, shared berth and rail proof, unresolved duplicate candidates.
SELECT jsonb_pretty(jsonb_build_object(
 'cli_terminals',(SELECT jsonb_agg(jsonb_build_object('id',a.asset_id,'name',a.name,'operator',a.operator_entity_id,'parent_port',t.parent_port_asset_id,'shared_tegram',t.metadata->>'tegram_shared_terminal_asset_id')) FROM public.pc_assets a JOIN public.pc_terminal_details t ON t.asset_id=a.asset_id WHERE a.asset_id IN ('ASSET_V125_004','ASSET_E474094DC4F76BBFEBF5')),
 'tegram_shared',(SELECT jsonb_agg(jsonb_build_object('id',t.asset_id,'parent_port',t.parent_port_asset_id,'berths',(SELECT jsonb_agg(jsonb_build_object('id',b.asset_id,'code',b.berth_code)) FROM public.pc_berth_details b WHERE b.terminal_asset_id=t.asset_id),'rail_interface',t.metadata->>'shared_rail_node_asset_id')) FROM public.pc_terminal_details t WHERE t.asset_id=(SELECT metadata->>'tegram_shared_terminal_asset_id' FROM public.pc_terminal_details WHERE asset_id='ASSET_V125_004')),
 'identity_exceptions',jsonb_build_array('ASSET_10C0070D509EDB385229: reconcile CLI Norte duplicate before merge','ASSET_V125_005: reconcile CLI Sul duplicate before merge','CLI Sul individual berth identities still require verified concession plan','No track geometry or exclusive TEGRAM berth ownership inferred')
)) AS result;
