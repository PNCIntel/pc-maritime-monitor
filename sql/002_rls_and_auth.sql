-- P&C tenant isolation and product entitlement helpers
begin;

create or replace function pc_is_super_admin()
returns boolean language sql stable security definer set search_path=public as $$
  select exists(
    select 1 from pc_profiles p
    where p.user_id=auth.uid() and p.active and p.global_role in ('super_admin','staff')
  );
$$;

create or replace function pc_user_org_ids()
returns setof uuid language sql stable security definer set search_path=public as $$
  select m.organization_id from pc_organization_members m
  where m.user_id=auth.uid() and m.active;
$$;

create or replace function pc_has_org_role(p_org uuid, p_roles text[])
returns boolean language sql stable security definer set search_path=public as $$
  select pc_is_super_admin() or exists(
    select 1 from pc_organization_members m
    where m.organization_id=p_org and m.user_id=auth.uid() and m.active and m.role=any(p_roles)
  );
$$;

create or replace function pc_has_product_access(p_product text)
returns boolean language sql stable security definer set search_path=public as $$
  select pc_is_super_admin() or exists(
    select 1
    from pc_organization_members m
    join pc_organization_entitlements e on e.organization_id=m.organization_id
    where m.user_id=auth.uid() and m.active and e.active
      and e.product_code=upper(p_product)
      and (e.start_date is null or e.start_date<=current_date)
      and (e.end_date is null or e.end_date>=current_date)
  );
$$;

-- Tenant tables
alter table pc_organizations enable row level security;
alter table pc_profiles enable row level security;
alter table pc_organization_members enable row level security;
alter table pc_organization_entitlements enable row level security;
alter table pc_saved_queries enable row level security;
alter table pc_saved_watchlists enable row level security;
alter table pc_watchlist_items enable row level security;
alter table pc_ai_sessions enable row level security;
alter table pc_ai_messages enable row level security;
alter table pc_scenario_runs enable row level security;
alter table pc_client_notes enable row level security;
alter table pc_client_admin_requests enable row level security;

-- Recreate policies idempotently.
do $$ declare r record; begin
  for r in select schemaname,tablename,policyname from pg_policies where schemaname='public' and policyname like 'pc_%' loop
    execute format('drop policy if exists %I on %I.%I',r.policyname,r.schemaname,r.tablename);
  end loop;
end $$;

create policy pc_org_read on pc_organizations for select
using (pc_is_super_admin() or organization_id in (select pc_user_org_ids()));

create policy pc_profile_self on pc_profiles for select
using (pc_is_super_admin() or user_id=auth.uid());

create policy pc_members_read on pc_organization_members for select
using (pc_is_super_admin() or organization_id in (select pc_user_org_ids()));

create policy pc_entitlements_read on pc_organization_entitlements for select
using (pc_is_super_admin() or organization_id in (select pc_user_org_ids()));

-- Saved queries / AI work are private to the user, while P&C staff can support all tenants.
create policy pc_queries_read on pc_saved_queries for select
using (pc_is_super_admin() or user_id=auth.uid());
create policy pc_queries_insert on pc_saved_queries for insert
with check (pc_is_super_admin() or (user_id=auth.uid() and organization_id in (select pc_user_org_ids())));
create policy pc_queries_update on pc_saved_queries for update
using (pc_is_super_admin() or user_id=auth.uid())
with check (pc_is_super_admin() or user_id=auth.uid());
create policy pc_queries_delete on pc_saved_queries for delete
using (pc_is_super_admin() or user_id=auth.uid());

-- Watchlists can be read by the tenant; analyst-or-higher roles can maintain them.
create policy pc_watchlists_read on pc_saved_watchlists for select
using (pc_is_super_admin() or organization_id in (select pc_user_org_ids()));
create policy pc_watchlists_write on pc_saved_watchlists for all
using (pc_is_super_admin() or pc_has_org_role(organization_id,array['org_admin','senior_analyst','analyst']))
with check (pc_is_super_admin() or pc_has_org_role(organization_id,array['org_admin','senior_analyst','analyst']));

create policy pc_watchitems_read on pc_watchlist_items for select using (
  pc_is_super_admin() or exists(
    select 1 from pc_saved_watchlists w
    where w.watchlist_id=pc_watchlist_items.watchlist_id
      and w.organization_id in (select pc_user_org_ids())
  )
);
create policy pc_watchitems_write on pc_watchlist_items for all using (
  pc_is_super_admin() or exists(
    select 1 from pc_saved_watchlists w
    where w.watchlist_id=pc_watchlist_items.watchlist_id
      and pc_has_org_role(w.organization_id,array['org_admin','senior_analyst','analyst'])
  )
) with check (
  pc_is_super_admin() or exists(
    select 1 from pc_saved_watchlists w
    where w.watchlist_id=pc_watchlist_items.watchlist_id
      and pc_has_org_role(w.organization_id,array['org_admin','senior_analyst','analyst'])
  )
);

create policy pc_sessions_read on pc_ai_sessions for select
using (pc_is_super_admin() or user_id=auth.uid());
create policy pc_sessions_insert on pc_ai_sessions for insert
with check (pc_is_super_admin() or (user_id=auth.uid() and organization_id in (select pc_user_org_ids())));
create policy pc_sessions_update on pc_ai_sessions for update
using (pc_is_super_admin() or user_id=auth.uid()) with check (pc_is_super_admin() or user_id=auth.uid());

create policy pc_messages_read on pc_ai_messages for select using (
  pc_is_super_admin() or exists(select 1 from pc_ai_sessions s where s.session_id=pc_ai_messages.session_id and s.user_id=auth.uid())
);
create policy pc_messages_insert on pc_ai_messages for insert with check (
  pc_is_super_admin() or exists(select 1 from pc_ai_sessions s where s.session_id=pc_ai_messages.session_id and s.user_id=auth.uid())
);

create policy pc_scenarios_read on pc_scenario_runs for select
using (pc_is_super_admin() or user_id=auth.uid());
create policy pc_scenarios_insert on pc_scenario_runs for insert
with check (pc_is_super_admin() or (user_id=auth.uid() and organization_id in (select pc_user_org_ids())));

create policy pc_notes_read on pc_client_notes for select
using (pc_is_super_admin() or user_id=auth.uid() or (shared_with_org and organization_id in (select pc_user_org_ids())));
create policy pc_notes_write on pc_client_notes for all
using (pc_is_super_admin() or user_id=auth.uid())
with check (pc_is_super_admin() or (user_id=auth.uid() and organization_id in (select pc_user_org_ids())));

-- Only the tenant's org admin can request account changes; P&C staff approves them.
create policy pc_admin_requests_read on pc_client_admin_requests for select
using (pc_is_super_admin() or pc_has_org_role(organization_id,array['org_admin']));
create policy pc_admin_requests_insert on pc_client_admin_requests for insert
with check (pc_is_super_admin() or (requested_by=auth.uid() and pc_has_org_role(organization_id,array['org_admin'])));

-- Shared canonical tables are readable to authenticated users. Product UI gating is enforced
-- by pc_has_product_access() in the Streamlit apps and by the product views below.
-- Writes remain service-role/admin only because no insert/update/delete policy is created.

alter table pc_sources enable row level security;
drop policy if exists pc_shared_read on pc_sources;
create policy pc_shared_read on pc_sources for select to authenticated using (true);
alter table pc_entities enable row level security;
drop policy if exists pc_shared_read on pc_entities;
create policy pc_shared_read on pc_entities for select to authenticated using (true);
alter table pc_entity_aliases enable row level security;
drop policy if exists pc_shared_read on pc_entity_aliases;
create policy pc_shared_read on pc_entity_aliases for select to authenticated using (true);
alter table pc_assets enable row level security;
drop policy if exists pc_shared_read on pc_assets;
create policy pc_shared_read on pc_assets for select to authenticated using (true);
alter table pc_mobile_assets enable row level security;
drop policy if exists pc_shared_read on pc_mobile_assets;
create policy pc_shared_read on pc_mobile_assets for select to authenticated using (true);
alter table pc_relationships enable row level security;
drop policy if exists pc_shared_read on pc_relationships;
create policy pc_shared_read on pc_relationships for select to authenticated using (true);
alter table pc_geographies enable row level security;
drop policy if exists pc_shared_read on pc_geographies;
create policy pc_shared_read on pc_geographies for select to authenticated using (true);
alter table pc_events enable row level security;
drop policy if exists pc_shared_read on pc_events;
create policy pc_shared_read on pc_events for select to authenticated using (true);
alter table pc_event_locations enable row level security;
drop policy if exists pc_shared_read on pc_event_locations;
create policy pc_shared_read on pc_event_locations for select to authenticated using (true);
alter table pc_event_links enable row level security;
drop policy if exists pc_shared_read on pc_event_links;
create policy pc_shared_read on pc_event_links for select to authenticated using (true);
alter table pc_impact_chains enable row level security;
drop policy if exists pc_shared_read on pc_impact_chains;
create policy pc_shared_read on pc_impact_chains for select to authenticated using (true);
alter table pc_governance_links enable row level security;
drop policy if exists pc_shared_read on pc_governance_links;
create policy pc_shared_read on pc_governance_links for select to authenticated using (true);
alter table pc_transactions enable row level security;
drop policy if exists pc_shared_read on pc_transactions;
create policy pc_shared_read on pc_transactions for select to authenticated using (true);
alter table pc_financial_records enable row level security;
drop policy if exists pc_shared_read on pc_financial_records;
create policy pc_shared_read on pc_financial_records for select to authenticated using (true);
alter table pc_market_data enable row level security;
drop policy if exists pc_shared_read on pc_market_data;
create policy pc_shared_read on pc_market_data for select to authenticated using (true);
alter table pc_security_compliance enable row level security;
drop policy if exists pc_shared_read on pc_security_compliance;
create policy pc_shared_read on pc_security_compliance for select to authenticated using (true);
alter table pc_analysis enable row level security;
drop policy if exists pc_shared_read on pc_analysis;
create policy pc_shared_read on pc_analysis for select to authenticated using (true);
alter table pc_legacy_sheet_rows enable row level security;
drop policy if exists pc_shared_read on pc_legacy_sheet_rows;
create policy pc_shared_read on pc_legacy_sheet_rows for select to authenticated using (true);

commit;
