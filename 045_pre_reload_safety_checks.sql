-- Power & Corridors
-- 045_pre_reload_safety_checks.sql
-- Purpose: one preflight gate before reloading Excel packages.
-- Does not change canonical data.

begin;

create or replace view public.pc_v_pre_reload_gate as
with checks as (
    select
        'duplicate_imo_mmsi_groups'::text as check_name,
        count(*)::bigint as issue_count,
        'BLOCK'::text as severity,
        'Resolve duplicate strong vessel identifiers before reload.'::text as guidance
    from public.pc_v_duplicate_mobile_asset_identifiers

    union all
    select
        'duplicate_exact_asset_groups',
        count(*),
        'BLOCK',
        'Review/merge exact duplicate fixed assets such as duplicated ports or terminals.'
    from public.pc_v_duplicate_asset_candidates

    union all
    select
        'duplicate_exact_entity_groups',
        count(*),
        'REVIEW',
        'Review duplicate company/entity groups before high-volume reload.'
    from public.pc_v_duplicate_entity_candidates

    union all
    select
        'duplicate_exact_mobile_asset_groups',
        count(*),
        'REVIEW',
        'Review duplicate vessel/mobile-asset groups; IMO/MMSI remain authoritative.'
    from public.pc_v_duplicate_mobile_asset_candidates

    union all
    select
        'fuzzy_asset_pairs',
        count(*),
        'REVIEW',
        'Review likely misspellings/variants such as Zayed/Zayad Port.'
    from public.pc_v_fuzzy_asset_name_candidates
)
select
    check_name,
    issue_count,
    severity,
    guidance,
    case
        when severity='BLOCK' and issue_count>0 then false
        else true
    end as reload_allowed_for_check
from checks;

create or replace function public.pc_pre_reload_status()
returns jsonb
language sql
stable
as $$
    select jsonb_build_object(
        'reload_allowed',
        not exists (
            select 1
            from public.pc_v_pre_reload_gate
            where severity='BLOCK'
              and issue_count>0
        ),
        'checks',
        coalesce(jsonb_agg(to_jsonb(g) order by severity desc,check_name),'[]'::jsonb)
    )
    from public.pc_v_pre_reload_gate g;
$$;

grant select on public.pc_v_pre_reload_gate to authenticated;
grant execute on function public.pc_pre_reload_status() to authenticated;

commit;

-- Run before reload:
-- select * from public.pc_v_pre_reload_gate;
-- select public.pc_pre_reload_status();
