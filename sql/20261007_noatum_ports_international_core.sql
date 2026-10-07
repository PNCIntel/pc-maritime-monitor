-- Power & Corridors
-- Noatum Ports international portfolio - first structured build
-- 2026-10-07
--
-- Scope:
--   Africa, Egypt/Jordan, Pakistan, Kazakhstan, Tanzania, Brazil and a first
--   current Spain terminal block.
--
-- Design:
--   * source-backed
--   * idempotent
--   * fixed terminal assets in pc_assets
--   * operating/legal entities in pc_entities
--   * Noatum Ports -> terminal links in pc_company_asset_roles
--   * local operating-company relationships in pc_company_relationships
--   * spatial columns populated with port-area coordinates for mapping
--     and explicitly marked as port-area precision pending terminal-footprint
--     verification.
--
-- Primary sources are embedded per assertion / asset.

begin;

-- ---------------------------------------------------------------------------
-- 1. Ensure Noatum Ports and key local operating companies exist
-- ---------------------------------------------------------------------------

with seed(entity_id,name,subtype,hq_city,hq_country,source_url) as (
  values
    ('COMP_NOATUM_PORTS','Noatum Ports','ports_operating_company',null,null,
     'https://www.adportsgroup.com/-/media/sites/adports/investors/annual-report/adpg-annual-report-2025-en.pdf?rev=8ae45f37905f4b779de70bd1544401b9'),
    ('COMP_KGTL','Karachi Gateway Terminal Limited','terminal_operating_company','Karachi','Pakistan',
     'https://www.adportsgroup.com/en/news-and-media/2025/09/02/ad-ports-groups-karachi-terminals-in-pakistan-sign-major-dredging-agreement'),
    ('COMP_KGTML','Karachi Gateway Terminal Multipurpose Limited','terminal_operating_company','Karachi','Pakistan',
     'https://www.adportsgroup.com/en/news-and-media/2025/12/05/karachi-gateway-multipurpose-terminal-and-louis-dreyfus-company-sign-long-term-agreement'),
    ('COMP_SARZHA_GRAIN_TERMINAL','Sarzha Grain Terminal','terminal_operating_company','Kuryk','Kazakhstan',
     'https://www.adportsgroup.com/en/news-and-media/2025/01/14/ad-ports-group-to-invest-in-greenfield-sarzha-grain-terminal-in-kuryk-port-kazakhstan'),
    ('COMP_TERMINAL_MARITIMA_CARTAGENA','Terminal Maritima de Cartagena','terminal_operating_company','Cartagena','Spain',
     'https://www.noatum.com/en/terminals-port-operations/terminales-maritimos-de-cartagena/')
)
insert into public.pc_entities(
  entity_id,name,entity_type,subtype,hq_city,hq_country,status,
  record_status,data_quality,as_of,metadata
)
select
  s.entity_id,s.name,'company',s.subtype,s.hq_city,s.hq_country,'active',
  'provisional','high',date '2026-10-07',
  jsonb_build_object(
    'research_program','NOATUM_PORTS_GLOBAL_BUILD_2026',
    'research_sources',jsonb_build_array(s.source_url),
    'source_quality','official'
  )
from seed s
where not exists (
  select 1 from public.pc_entities e
  where e.entity_id=s.entity_id
     or lower(trim(e.name))=lower(trim(s.name))
);

-- ---------------------------------------------------------------------------
-- 2. Corporate operating relationships beneath Noatum Ports
-- ---------------------------------------------------------------------------

with rel(parent_company_key,child_company_key,relationship,value,unit,effective_from,source_url,notes,metadata) as (
  values
    ('COMP_NOATUM_PORTS','COMP_KGTL','controlled_interest',60::numeric,'percent',null::date,
     'https://www.adportsgroup.com/-/media/sites/adports/investors/2025/downloads/adpg--2025-capital-market-day-consolidated.pdf?rev=-1',
     'Karachi container terminal concession; AD Ports Group / Noatum Ports economic interest reported at 60%.',
     jsonb_build_object('concession_years',50,'terminal_type','container')),
    ('COMP_NOATUM_PORTS','COMP_KGTML','controlled_interest',60::numeric,'percent',null::date,
     'https://www.adportsgroup.com/-/media/sites/adports/investors/2025/downloads/adpg--2025-capital-market-day-consolidated.pdf?rev=-1',
     'Karachi multipurpose terminal concession; AD Ports Group / Noatum Ports economic interest reported at 60%.',
     jsonb_build_object('concession_years',25,'terminal_type','multipurpose')),
    ('COMP_NOATUM_PORTS','COMP_SARZHA_GRAIN_TERMINAL','controlled_interest',51::numeric,'percent',date '2025-01-14',
     'https://www.adportsgroup.com/en/news-and-media/2025/01/14/ad-ports-group-to-invest-in-greenfield-sarzha-grain-terminal-in-kuryk-port-kazakhstan',
     'AD Ports Group owns 51% of the Sarzha Grain Terminal partnership; Semurg owns 49%.',
     jsonb_build_object('partner','SEMURG INVEST LLP')),
    ('COMP_NOATUM_PORTS','COMP_CLI','operator',null::numeric,null,date '2026-10-02',
     'https://www.adportsgroup.com/en/news-and-media/2026/10/02/ad-ports-group-successfully-completes-acquisition-of-brazils-cli',
     'Noatum Ports assumed operational control of CLI at financial close.',
     jsonb_build_object('role_detail','operational_control'))
)
insert into public.pc_company_relationships(
  parent_company_key,child_company_key,relationship,value,unit,
  effective_from,confidence,source_url,notes,metadata
)
select
  r.parent_company_key,r.child_company_key,r.relationship,r.value,r.unit,
  r.effective_from,'high',r.source_url,r.notes,r.metadata
from rel r
where exists(select 1 from public.pc_entities e where e.entity_id=r.parent_company_key)
  and exists(select 1 from public.pc_entities e where e.entity_id=r.child_company_key)
  and not exists (
    select 1 from public.pc_company_relationships x
    where x.parent_company_key=r.parent_company_key
      and x.child_company_key=r.child_company_key
      and lower(x.relationship)=lower(r.relationship)
      and coalesce(x.effective_from,date '1900-01-01')=coalesce(r.effective_from,date '1900-01-01')
      and x.effective_to is null
  );

-- ---------------------------------------------------------------------------
-- 3. Terminal assets
--    latitude/longitude are port-area coordinates for immediate mapping.
--    metadata.spatial_precision makes clear they are not yet berth polygons.
-- ---------------------------------------------------------------------------

with seed(
  asset_id,name,subtype,country,region_city,latitude,longitude,status,
  capacity_value,capacity_unit,source_url,metadata
) as (
  values
    (
      'TERM_NOATUM_LUANDA',
      'Noatum Ports Luanda Terminal',
      'multipurpose_terminal','Angola','Luanda',
      -8.8074::numeric,13.2382::numeric,'active',
      350000::numeric,'TEU',
      'https://www.adportsgroup.com/en/news-and-media/2025/09/19/ad-ports-group-breaks-ground-on-noatum-ports-luanda-terminal',
      jsonb_build_object(
        'container_capacity_teu',350000,
        'roro_capacity_ceu',40000,
        'concession_years',20,
        'concession_extendable_to',2055,
        'initial_capex_usd',250000000,
        'potential_total_investment_usd',380000000,
        'terminal_area_sqm',192000,
        'depth_m',16,
        'operating_jv_interest_pct',81,
        'spatial_precision','port_area',
        'spatial_verification','terminal footprint refinement required'
      )
    ),
    (
      'TERM_NOATUM_POINTE_NOIRE',
      'Noatum Ports Pointe-Noire Terminal',
      'container_terminal','Republic of the Congo','Pointe-Noire',
      -4.7889::numeric,11.8478::numeric,'development',
      400000::numeric,'TEU',
      'https://www.adportsgroup.com/en/news-and-media/2026/05/18/ad-ports-group-awards-three-contracts-for-noatum-ports-pointe-noire-terminal',
      jsonb_build_object(
        'concession_years',30,
        'extension_years',20,
        'committed_capex_usd',220000000,
        'ad_ports_interest_pct',51,
        'partner','CMA Terminals / CMA CGM Group',
        'expected_start','Q3 2027',
        'spatial_precision','port_area',
        'spatial_verification','terminal footprint refinement required'
      )
    ),
    (
      'TERM_NOATUM_SAFAGA',
      'Noatum Ports Safaga Terminal',
      'multipurpose_terminal','Egypt','Safaga',
      26.7420::numeric,33.9400::numeric,'trial_operations',
      450000::numeric,'TEU',
      'https://www.adportsgroup.com/en/news-and-media/2026/06/08/ad-ports-group-launches-trial-operations-at-noatum-ports-safaga-terminal-in-egypt',
      jsonb_build_object(
        'container_capacity_teu',450000,
        'dry_bulk_general_cargo_tons',5000000,
        'liquid_bulk_tons',1000000,
        'roro_capacity_ceu',50000,
        'committed_capex_usd',200000000,
        'concession_years',30,
        'sts_cranes',3,
        'rtg_cranes',6,
        'trial_operations_date','2026-06-09',
        'spatial_precision','port_area',
        'spatial_verification','terminal footprint refinement required'
      )
    ),
    (
      'TERM_NOATUM_ADABIYA',
      'Noatum Ports Adabiya Terminal',
      'multipurpose_terminal','Egypt','Adabiya',
      29.8580::numeric,32.4700::numeric,'active',
      150000::numeric,'TEU',
      'https://www.adportsgroup.com/-/media/sites/adports/investors/2025/downloads/adpg--2025-capital-market-day-consolidated.pdf?rev=-1',
      jsonb_build_object(
        'management_contract',true,
        'ownership_interest_pct',70,
        'dry_bulk_general_cargo_tons',3000000,
        'spatial_precision','port_area',
        'spatial_verification','terminal footprint refinement required'
      )
    ),
    (
      'TERM_KGTL_KARACHI',
      'Karachi Gateway Terminal',
      'container_terminal','Pakistan','Karachi',
      24.8150::numeric,66.9760::numeric,'active',
      1000000::numeric,'TEU',
      'https://www.adportsgroup.com/en/news-and-media/2025/09/02/ad-ports-groups-karachi-terminals-in-pakistan-sign-major-dredging-agreement',
      jsonb_build_object(
        'operating_company_entity_id','COMP_KGTL',
        'historic_capacity_teu',750000,
        'expanded_capacity_teu',1000000,
        'maximum_vessel_length_m',350,
        'target_draft_m',15.5,
        'concession_years',50,
        'spatial_precision','port_area',
        'spatial_verification','terminal footprint refinement required'
      )
    ),
    (
      'TERM_KGTML_KARACHI',
      'Karachi Gateway Terminal Multipurpose',
      'multipurpose_terminal','Pakistan','Karachi',
      24.8155::numeric,66.9780::numeric,'active',
      14000000::numeric,'tonnes_per_year',
      'https://www.adportsgroup.com/en/news-and-media/2025/12/05/karachi-gateway-multipurpose-terminal-and-louis-dreyfus-company-sign-long-term-agreement',
      jsonb_build_object(
        'operating_company_entity_id','COMP_KGTML',
        'dry_bulk_general_cargo_capacity_tons',14000000,
        'phase_one_capex_usd',75000000,
        'concession_years',25,
        'ldc_clean_bulk_facility',true,
        'spatial_precision','port_area',
        'spatial_verification','terminal footprint refinement required'
      )
    ),
    (
      'TERM_NOATUM_DAR_ES_SALAAM',
      'Noatum Ports Dar es Salaam Container Terminal',
      'container_terminal','Tanzania','Dar es Salaam',
      -6.8230::numeric,39.2920::numeric,'active',
      1000000::numeric,'TEU',
      'https://www.adportsgroup.com/-/media/sites/adports/investors/2025/downloads/adpg--2025-capital-market-day-consolidated.pdf?rev=-1',
      jsonb_build_object(
        'economic_interest_pct',30,
        'concession_years',30,
        'committed_capex_usd_min',20000000,
        'spatial_precision','port_area',
        'spatial_verification','terminal footprint refinement required'
      )
    ),
    (
      'TERM_SARZHA_GRAIN_KURYK',
      'Sarzha Grain Terminal',
      'grain_terminal','Kazakhstan','Kuryk',
      43.1880::numeric,51.6510::numeric,'development',
      570000::numeric,'tonnes_per_year',
      'https://www.adportsgroup.com/en/news-and-media/2025/01/14/ad-ports-group-to-invest-in-greenfield-sarzha-grain-terminal-in-kuryk-port-kazakhstan',
      jsonb_build_object(
        'phase_one_capacity_tons',570000,
        'phase_two_capacity_tons',1500000,
        'ad_ports_interest_pct',51,
        'semurg_interest_pct',49,
        'total_investment_usd',50000000,
        'ad_ports_contribution_usd',30000000,
        'spatial_precision','port_area',
        'spatial_verification','terminal footprint refinement required'
      )
    ),
    (
      'TERM_AQABA_MULTIPURPOSE',
      'Aqaba Multipurpose Port',
      'multipurpose_terminal','Jordan','Aqaba',
      29.4750::numeric,34.9930::numeric,'concession_signed',
      null::numeric,null,
      'https://www.adportsgroup.com/en/news-and-media/2026/02/05/ad-ports-group-signs-30-year-agreement-with-aqaba-development-corporation',
      jsonb_build_object(
        'concession_years',30,
        'ad_ports_jv_interest_pct',70,
        'aqaba_development_corporation_interest_pct',30,
        'ad_ports_investment_aed',141000000,
        'ad_ports_investment_usd',38400000,
        'spatial_precision','port_area',
        'spatial_verification','terminal footprint refinement required'
      )
    ),
    (
      'TERM_DOUALA_DRY_BULK',
      'Douala New Dry Bulk Terminal',
      'dry_bulk_terminal','Cameroon','Douala',
      4.0500::numeric,9.6750::numeric,'development',
      null::numeric,null,
      'https://www.adportsgroup.com/en/news-and-media/2026/02/12/ad-ports-group-enters-into-30-year-concession-agreement-with-africa-ports-development',
      jsonb_build_object(
        'concession_years',30,
        'ad_ports_effective_interest_pct',51,
        'uae_investor_group_interest_pct',60,
        'africa_ports_development_interest_pct',40,
        'spatial_precision','port_area',
        'spatial_verification','terminal footprint refinement required'
      )
    ),
    (
      'TERM_CLI_NORTE_ITAQUI',
      'CLI Norte Terminal',
      'agri_bulk_terminal','Brazil','Itaqui / Sao Luis',
      -2.5660::numeric,-44.3670::numeric,'active',
      null::numeric,null,
      'https://www.adportsgroup.com/en/news-and-media/2026/10/02/ad-ports-group-successfully-completes-acquisition-of-brazils-cli',
      jsonb_build_object(
        'operating_company_entity_id','COMP_CLI_NORTE',
        'cli_ownership_pct',100,
        'cargo_focus',jsonb_build_array('grain','agri-bulk'),
        'corridor','Arc of the North',
        'spatial_precision','port_area',
        'spatial_verification','terminal footprint refinement required'
      )
    ),
    (
      'TERM_CLI_SUL_SANTOS',
      'CLI Sul Terminal',
      'agri_bulk_terminal','Brazil','Santos',
      -23.9550::numeric,-46.3260::numeric,'active',
      null::numeric,null,
      'https://www.adportsgroup.com/en/news-and-media/2026/10/02/ad-ports-group-successfully-completes-acquisition-of-brazils-cli',
      jsonb_build_object(
        'operating_company_entity_id','COMP_CLI_SUL',
        'cli_ownership_pct',80,
        'cargo_focus',jsonb_build_array('sugar','corn','soybeans','agri-bulk'),
        'spatial_precision','port_area',
        'spatial_verification','terminal footprint refinement required'
      )
    ),

    -- Current Noatum-branded Spain terminals with dedicated official pages.
    (
      'TERM_NOATUM_SANTANDER',
      'Noatum Ports Santander Terminal',
      'multipurpose_terminal','Spain','Santander',
      43.4540::numeric,-3.8120::numeric,'active',
      null::numeric,null,
      'https://www.noatum.com/en/terminals-port-operations/noatum-ports-santander-terminal/',
      jsonb_build_object(
        'total_area_sqm',63000,
        'vehicle_public_area_sqm',280000,
        'storage_area_sqm',46000,
        'berthing_line_m',3100,
        'depth_m',13,
        'roro_ramps',3,
        'rail_tracks',4,
        'cargo_types',jsonb_build_array('bulk','multipurpose','ro-ro','automotive'),
        'spatial_precision','port_area',
        'spatial_verification','terminal footprint refinement required'
      )
    ),
    (
      'TERM_NOATUM_MALAGA',
      'Noatum Ports Malaga Terminal',
      'multipurpose_terminal','Spain','Malaga',
      36.7110::numeric,-4.4200::numeric,'active',
      null::numeric,null,
      'https://www.noatum.com/en/terminals-port-operations/noatum-ports-malaga-terminal/',
      jsonb_build_object(
        'total_area_sqm',365914,
        'storage_area_sqm',42000,
        'berthing_line_m',723,
        'roro_berthing_m',175,
        'vehicle_storage_sqm',100000,
        'depth_m',16,
        'reefer_plugs',516,
        'rail_terminals',2,
        'cargo_types',jsonb_build_array('container','bulk','multipurpose','ro-ro','automotive'),
        'spatial_precision','port_area',
        'spatial_verification','terminal footprint refinement required'
      )
    ),
    (
      'TERM_NOATUM_CASTELLON',
      'Noatum Ports Castellon Terminal',
      'multipurpose_terminal','Spain','Castellon',
      39.9710::numeric,0.0190::numeric,'active',
      250000::numeric,'TEU',
      'https://www.noatum.com/en/terminals-port-operations/noatum-ports-castellon-terminal/',
      jsonb_build_object(
        'total_area_sqm',214235,
        'storage_area_sqm',15000,
        'berthing_line_m',990,
        'depth_min_m',11.5,
        'depth_max_m',13,
        'reefer_plugs',144,
        'sts_cranes',5,
        'rail_connected',true,
        'annual_container_potential_teu',250000,
        'bulk_capacity_tons',2000000,
        'acquired_from','APM Terminals',
        'acquisition_date','2024-01-02',
        'spatial_precision','port_area',
        'spatial_verification','terminal footprint refinement required'
      )
    ),
    (
      'TERM_NOATUM_TARRAGONA',
      'Noatum Ports Tarragona Terminal',
      'multipurpose_terminal','Spain','Tarragona',
      41.1010::numeric,1.2330::numeric,'active',
      null::numeric,null,
      'https://www.noatum.com/en/terminals-port-operations/noatum-ports-tarragona-terminal/',
      jsonb_build_object(
        'total_area_sqm',72000,
        'storage_area_sqm',55916,
        'berthing_line_m',5000,
        'depth_min_m',12,
        'depth_max_m',16,
        'roro_ramps',2,
        'rail_access',true,
        'grain_import_role',true,
        'cargo_types',jsonb_build_array('bulk','general cargo','ro-ro','automotive'),
        'spatial_precision','port_area',
        'spatial_verification','terminal footprint refinement required'
      )
    ),
    (
      'TERM_NOATUM_SAGUNTO',
      'Noatum Ports Sagunto Terminal',
      'multipurpose_terminal','Spain','Sagunto',
      39.6410::numeric,-0.2110::numeric,'active',
      null::numeric,null,
      'https://www.noatum.com/en/noatum-automotive/noatum-ports-sagunto-terminal/',
      jsonb_build_object(
        'total_area_sqm',256812,
        'vehicle_area_sqm',100000,
        'berthing_line_m',1530,
        'depth_min_m',10,
        'depth_max_m',12.7,
        'roro_ramps',1,
        'vehicle_space_sqm',45000,
        'cargo_types',jsonb_build_array('ro-ro','automotive','multipurpose','agri-bulk'),
        'spatial_precision','port_area',
        'spatial_verification','terminal footprint refinement required'
      )
    ),
    (
      'TERM_NOATUM_CARTAGENA',
      'Terminal Maritima de Cartagena',
      'multipurpose_terminal','Spain','Cartagena',
      37.5840::numeric,-0.9860::numeric,'active',
      null::numeric,null,
      'https://www.noatum.com/en/terminals-port-operations/terminales-maritimos-de-cartagena/',
      jsonb_build_object(
        'total_area_sqm',60279,
        'storage_area_sqm',31000,
        'berthing_line_m',800,
        'depth_m',11,
        'sts_cranes',3,
        'cargo_types',jsonb_build_array('container','project cargo','multipurpose'),
        'spatial_precision','port_area',
        'spatial_verification','terminal footprint refinement required'
      )
    )
)
insert into public.pc_assets(
  asset_id,name,asset_type,subtype,country,region_city,latitude,longitude,
  capacity_value,capacity_unit,status,record_status,data_quality,metadata
)
select
  s.asset_id,s.name,'port_terminal',s.subtype,s.country,s.region_city,s.latitude,s.longitude,
  s.capacity_value,s.capacity_unit,s.status,'provisional','high',
  coalesce(s.metadata,'{}'::jsonb) || jsonb_build_object(
    'research_program','NOATUM_PORTS_GLOBAL_BUILD_2026',
    'research_sources',jsonb_build_array(s.source_url),
    'source_quality','official',
    'as_of','2026-10-07'
  )
from seed s
where not exists (
  select 1 from public.pc_assets a
  where a.asset_id=s.asset_id
     or (
       lower(trim(a.name))=lower(trim(s.name))
       and lower(coalesce(a.country,''))=lower(coalesce(s.country,''))
     )
);

-- ---------------------------------------------------------------------------
-- 4. Noatum Ports operating-role edges to every terminal above
-- ---------------------------------------------------------------------------

with targets(asset_id) as (
  values
    ('TERM_NOATUM_LUANDA'),
    ('TERM_NOATUM_POINTE_NOIRE'),
    ('TERM_NOATUM_SAFAGA'),
    ('TERM_NOATUM_ADABIYA'),
    ('TERM_KGTL_KARACHI'),
    ('TERM_KGTML_KARACHI'),
    ('TERM_NOATUM_DAR_ES_SALAAM'),
    ('TERM_SARZHA_GRAIN_KURYK'),
    ('TERM_AQABA_MULTIPURPOSE'),
    ('TERM_DOUALA_DRY_BULK'),
    ('TERM_CLI_NORTE_ITAQUI'),
    ('TERM_CLI_SUL_SANTOS'),
    ('TERM_NOATUM_SANTANDER'),
    ('TERM_NOATUM_MALAGA'),
    ('TERM_NOATUM_CASTELLON'),
    ('TERM_NOATUM_TARRAGONA'),
    ('TERM_NOATUM_SAGUNTO'),
    ('TERM_NOATUM_CARTAGENA')
)
insert into public.pc_company_asset_roles(
  entity_id,asset_id,asset_role,role_status,as_of,metadata
)
select
  'COMP_NOATUM_PORTS',
  a.asset_id,
  'operator',
  'reported',
  date '2026-10-07',
  jsonb_build_object(
    'research_program','NOATUM_PORTS_GLOBAL_BUILD_2026',
    'role_detail','international_ports_operating_arm',
    'confidence','high',
    'research_sources',coalesce(a.metadata->'research_sources','[]'::jsonb)
  )
from targets t
join public.pc_assets a on a.asset_id=t.asset_id
where exists(select 1 from public.pc_entities e where e.entity_id='COMP_NOATUM_PORTS')
and not exists (
  select 1 from public.pc_company_asset_roles r
  where r.entity_id='COMP_NOATUM_PORTS'
    and r.asset_id=a.asset_id
    and r.asset_role='operator'
    and r.valid_to is null
);

-- ---------------------------------------------------------------------------
-- 5. Local company -> terminal roles where we have an exact operating entity
-- ---------------------------------------------------------------------------

with rel(entity_id,asset_id,asset_role,detail,source_url) as (
  values
    ('COMP_KGTL','TERM_KGTL_KARACHI','operator','local_terminal_operating_company',
     'https://www.adportsgroup.com/en/news-and-media/2025/09/02/ad-ports-groups-karachi-terminals-in-pakistan-sign-major-dredging-agreement'),
    ('COMP_KGTML','TERM_KGTML_KARACHI','operator','local_terminal_operating_company',
     'https://www.adportsgroup.com/en/news-and-media/2025/12/05/karachi-gateway-multipurpose-terminal-and-louis-dreyfus-company-sign-long-term-agreement'),
    ('COMP_SARZHA_GRAIN_TERMINAL','TERM_SARZHA_GRAIN_KURYK','operator','joint_venture_terminal_company',
     'https://www.adportsgroup.com/en/news-and-media/2025/01/14/ad-ports-group-to-invest-in-greenfield-sarzha-grain-terminal-in-kuryk-port-kazakhstan'),
    ('COMP_CLI_NORTE','TERM_CLI_NORTE_ITAQUI','operator','cli_terminal_operating_company',
     'https://www.adportsgroup.com/en/news-and-media/2026/10/02/ad-ports-group-successfully-completes-acquisition-of-brazils-cli'),
    ('COMP_CLI_SUL','TERM_CLI_SUL_SANTOS','operator','cli_terminal_operating_company',
     'https://www.adportsgroup.com/en/news-and-media/2026/10/02/ad-ports-group-successfully-completes-acquisition-of-brazils-cli'),
    ('COMP_TERMINAL_MARITIMA_CARTAGENA','TERM_NOATUM_CARTAGENA','operator','local_terminal_operating_company',
     'https://www.noatum.com/en/terminals-port-operations/terminales-maritimos-de-cartagena/')
)
insert into public.pc_company_asset_roles(
  entity_id,asset_id,asset_role,role_status,as_of,metadata
)
select
  r.entity_id,r.asset_id,r.asset_role,'reported',date '2026-10-07',
  jsonb_build_object(
    'role_detail',r.detail,
    'confidence','high',
    'research_sources',jsonb_build_array(r.source_url)
  )
from rel r
where exists(select 1 from public.pc_entities e where e.entity_id=r.entity_id)
  and exists(select 1 from public.pc_assets a where a.asset_id=r.asset_id)
  and not exists (
    select 1 from public.pc_company_asset_roles x
    where x.entity_id=r.entity_id
      and x.asset_id=r.asset_id
      and x.asset_role=r.asset_role
      and x.valid_to is null
  );

-- ---------------------------------------------------------------------------
-- 6. Convenience operator pointers where empty
-- ---------------------------------------------------------------------------

update public.pc_assets a
set operator_entity_id='COMP_NOATUM_PORTS',
    updated_at=now()
where a.asset_id in (
  'TERM_NOATUM_LUANDA','TERM_NOATUM_POINTE_NOIRE','TERM_NOATUM_SAFAGA',
  'TERM_NOATUM_ADABIYA','TERM_KGTL_KARACHI','TERM_KGTML_KARACHI',
  'TERM_NOATUM_DAR_ES_SALAAM','TERM_SARZHA_GRAIN_KURYK',
  'TERM_AQABA_MULTIPURPOSE','TERM_DOUALA_DRY_BULK',
  'TERM_CLI_NORTE_ITAQUI','TERM_CLI_SUL_SANTOS',
  'TERM_NOATUM_SANTANDER','TERM_NOATUM_MALAGA','TERM_NOATUM_CASTELLON',
  'TERM_NOATUM_TARRAGONA','TERM_NOATUM_SAGUNTO','TERM_NOATUM_CARTAGENA'
)
and a.operator_entity_id is null;

commit;

-- ---------------------------------------------------------------------------
-- Verification A - Noatum Ports terminal footprint
-- ---------------------------------------------------------------------------

select
  a.name,
  a.country,
  a.region_city,
  a.subtype,
  a.status,
  a.capacity_value,
  a.capacity_unit,
  a.latitude,
  a.longitude
from public.pc_company_asset_roles r
join public.pc_assets a on a.asset_id=r.asset_id
where r.entity_id='COMP_NOATUM_PORTS'
  and r.asset_role='operator'
  and r.valid_to is null
order by a.country,a.name;

-- ---------------------------------------------------------------------------
-- Verification B - counts by country
-- ---------------------------------------------------------------------------

select
  a.country,
  count(distinct a.asset_id) as terminal_count
from public.pc_company_asset_roles r
join public.pc_assets a on a.asset_id=r.asset_id
where r.entity_id='COMP_NOATUM_PORTS'
  and r.asset_role='operator'
  and r.valid_to is null
group by a.country
order by terminal_count desc,a.country;

-- ---------------------------------------------------------------------------
-- Verification C - spatial gaps
-- ---------------------------------------------------------------------------

select a.asset_id,a.name,a.country,a.region_city
from public.pc_company_asset_roles r
join public.pc_assets a on a.asset_id=r.asset_id
where r.entity_id='COMP_NOATUM_PORTS'
  and r.asset_role='operator'
  and r.valid_to is null
  and (a.latitude is null or a.longitude is null)
order by a.country,a.name;
