-- Power & Corridors
-- 073_irving_asset_role_completion.sql
-- Completes the specialist company -> shipyard role for Irving Shipbuilding.
-- No capacity metric is invented.

begin;

insert into public.pc_company_asset_roles(
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
select
  gen_random_uuid(),
  'COMP_IRVING',
  a.asset_id,
  null,
  'operator',
  'active',
  null,
  null,
  current_date,
  null,
  null,
  jsonb_build_object(
    'materialisation','073',
    'basis','pc_assets.operator_entity_id and 072 Irving strategic-industrial materialisation',
    'inference',false
  )
from public.pc_assets a
where a.operator_entity_id='COMP_IRVING'
  and public.pc_norm_identity_text(a.name)=public.pc_norm_identity_text('Halifax Shipyard')
  and not exists (
    select 1
    from public.pc_company_asset_roles r
    where r.entity_id='COMP_IRVING'
      and r.asset_id=a.asset_id
      and lower(coalesce(r.asset_role,''))='operator'
      and r.valid_to is null
  );

select public.pc_normalize_canonical_relationships();
select public.pc_refresh_terminal_indexes();

do $$
begin
  if to_regprocedure('public.pc_refresh_terminal_industrial_links()') is not null then
    perform public.pc_refresh_terminal_industrial_links();
  end if;
end $$;

commit;

-- Validation:
-- select * from public.pc_model_audit_entity('COMP_IRVING');
-- select public.pc_strategic_entity_dossier('COMP_IRVING')->'counts';
