-- Power & Corridors
-- Noatum Ports Spain portfolio completion - official 2024 portfolio locations
-- 2026-10-07
--
-- Source basis:
-- Noatum Ports 2024 Sustainability Report identifies 17 terminal locations,
-- including the following Spain locations. Where a dedicated terminal page is
-- not yet available, these records are deliberately stored as portfolio-level
-- terminal locations with conservative subtype/metadata rather than invented
-- terminal-company detail.
--
-- Official source:
-- https://www.noatum.com/wp-content/uploads/2025/12/NOATUM-PORTS-INFORME_en_2024.pdf

begin;

drop table if exists pg_temp.pc_noatum_ports_ctx;
create temp table pc_noatum_ports_ctx(entity_id text primary key) on commit drop;

insert into pc_noatum_ports_ctx(entity_id)
select e.entity_id
from public.pc_entities e
where e.entity_id='COMP_NOATUM_PORTS'
   or lower(trim(e.name))=lower(trim('Noatum Ports'))
order by case when e.entity_id='COMP_NOATUM_PORTS' then 0 else 1 end,
         e.created_at nulls last
limit 1;

do $
begin
  if not exists (select 1 from pc_noatum_ports_ctx) then
    raise exception 'Noatum Ports entity is not present; run the international core SQL first';
  end if;
end $;

with seed(asset_id,name,region_city,latitude,longitude) as (
  values
    ('TERM_NOATUM_A_CORUNA','Noatum Ports - A Coruna','A Coruna',43.3600::numeric,-8.4000::numeric),
    ('TERM_NOATUM_FERROL','Noatum Ports - Ferrol','Ferrol',43.4700::numeric,-8.2500::numeric),
    ('TERM_NOATUM_AVILES','Noatum Ports - Aviles','Aviles',43.5900::numeric,-5.9400::numeric),
    ('TERM_NOATUM_GIJON','Noatum Ports - Gijon','Gijon',43.5600::numeric,-5.7000::numeric),
    ('TERM_NOATUM_BILBAO','Noatum Ports - Bilbao','Bilbao',43.3500::numeric,-3.0400::numeric),
    ('TERM_NOATUM_PASAJES','Noatum Ports - Pasajes','Pasajes / Pasaia',43.3200::numeric,-1.9200::numeric),
    ('TERM_NOATUM_VILAGARCIA','Noatum Ports - Vilagarcia','Vilagarcia de Arousa',42.6000::numeric,-8.7700::numeric),
    ('TERM_NOATUM_VIGO','Noatum Ports - Vigo','Vigo',42.2400::numeric,-8.7200::numeric),
    ('TERM_NOATUM_HUELVA','Noatum Ports - Huelva','Huelva',37.2000::numeric,-6.9500::numeric),
    ('TERM_NOATUM_BARCELONA','Noatum Ports - Barcelona','Barcelona',41.3500::numeric,2.1700::numeric)
)
insert into public.pc_assets(
  asset_id,name,asset_type,subtype,country,region_city,latitude,longitude,
  status,record_status,data_quality,metadata
)
select
  s.asset_id,s.name,'port_terminal','portfolio_terminal','Spain',s.region_city,
  s.latitude,s.longitude,'active','provisional','medium',
  jsonb_build_object(
    'research_program','NOATUM_PORTS_GLOBAL_BUILD_2026',
    'research_sources',jsonb_build_array(
      'https://www.noatum.com/wp-content/uploads/2025/12/NOATUM-PORTS-INFORME_en_2024.pdf'
    ),
    'source_quality','official',
    'portfolio_location_confirmed',true,
    'terminal_identity_detail','portfolio location confirmed; exact terminal operating-company/legal perimeter pending dedicated-source verification',
    'spatial_precision','port_area',
    'spatial_verification','terminal footprint refinement required',
    'as_of','2024-12-31'
  )
from seed s
where not exists (
  select 1
  from public.pc_assets a
  where a.asset_id=s.asset_id
     or (
       lower(trim(a.name))=lower(trim(s.name))
       and lower(coalesce(a.country,''))='spain'
     )
);

insert into public.pc_company_asset_roles(
  entity_id,asset_id,asset_role,role_status,as_of,metadata
)
select
  ctx.entity_id,
  s.asset_id,
  'operator',
  'reported',
  date '2024-12-31',
  jsonb_build_object(
    'role_detail','official_portfolio_terminal_location',
    'confidence','medium',
    'research_sources',jsonb_build_array(
      'https://www.noatum.com/wp-content/uploads/2025/12/NOATUM-PORTS-INFORME_en_2024.pdf'
    ),
    'verification_note','Noatum Ports official portfolio map confirms location; exact local operating company and terminal scope to be deepened.'
  )
from (
  values
    ('TERM_NOATUM_A_CORUNA'),
    ('TERM_NOATUM_FERROL'),
    ('TERM_NOATUM_AVILES'),
    ('TERM_NOATUM_GIJON'),
    ('TERM_NOATUM_BILBAO'),
    ('TERM_NOATUM_PASAJES'),
    ('TERM_NOATUM_VILAGARCIA'),
    ('TERM_NOATUM_VIGO'),
    ('TERM_NOATUM_HUELVA'),
    ('TERM_NOATUM_BARCELONA')
) as s(asset_id)
cross join pc_noatum_ports_ctx ctx
where exists(select 1 from public.pc_entities e where e.entity_id=ctx.entity_id)
  and exists(select 1 from public.pc_assets a where a.asset_id=s.asset_id)
  and not exists (
    select 1
    from public.pc_company_asset_roles r
    where r.entity_id=ctx.entity_id
      and r.asset_id=s.asset_id
      and r.asset_role='operator'
      and r.valid_to is null
  );

update public.pc_assets a
set operator_entity_id=ctx.entity_id,
    updated_at=now()
from pc_noatum_ports_ctx ctx
where a.asset_id in (
  'TERM_NOATUM_A_CORUNA','TERM_NOATUM_FERROL','TERM_NOATUM_AVILES',
  'TERM_NOATUM_GIJON','TERM_NOATUM_BILBAO','TERM_NOATUM_PASAJES',
  'TERM_NOATUM_VILAGARCIA','TERM_NOATUM_VIGO','TERM_NOATUM_HUELVA',
  'TERM_NOATUM_BARCELONA'
)
and a.operator_entity_id is null;

commit;

-- Verification
select
  a.name,a.country,a.region_city,a.subtype,a.status,a.latitude,a.longitude,
  r.role_status,r.metadata->>'confidence' as relationship_confidence
from public.pc_company_asset_roles r
join public.pc_assets a on a.asset_id=r.asset_id
where r.entity_id=ctx.entity_id
  and r.asset_role='operator'
  and a.country='Spain'
  and r.valid_to is null
order by a.region_city,a.name;
