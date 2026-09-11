# Power & Corridors — Supabase Migration Kit

**Build date:** 11 September 2026  
**Goal:** migrate the current Excel-backed P&C model into one Supabase/PostgreSQL core without breaking the existing client apps.

## Five Streamlit apps

1. `app.py` — **P&C Trade** client app (Excel/Supabase bridge)
2. `pc-intelligence.py` — **P&C Intelligence** client app (Excel/Supabase bridge + strict Intelligence event gate)
3. `pc-nerai.py` — **NERAI** client add-on scaffold
4. `pc-power-admin.py` — internal **P&C Power Admin** / super-admin / AI research / batch staging
5. `pc-client-admin.py` — shared client organization administration for Trade, Intelligence and NERAI

`pc_intelligence_app.py` is included as a compatibility copy of `pc-intelligence.py` for the existing Streamlit deployment path.

All five apps use the **same underlying data model**.

## Why the bridge exists

The current Trade and Intelligence apps expect workbook/sheet-shaped pandas DataFrames. Rewriting every page on migration night is unnecessary risk.

`shared/pc_data_bridge.py` uses this order:

1. Supabase `pc_legacy_sheet_rows` if configured/populated.
2. Existing `/data/*.xlsx` files as fallback.

That means we can migrate the data first, switch `PC_DATA_BACKEND=supabase`, verify both client apps, and then progressively replace legacy-sheet queries with normalized canonical table queries.

## Immediate product fixes included

### P&C Trade

A new **Alerts & Disruptions** workspace filters for commercial/operational disruption — weather, labour, port/rail/road disruption, customs/policy constraints, infrastructure incidents and security spillover — while excluding routine corporate development such as new terminals, cranes, acquisitions, vessel orders and service launches unless a real disruption is present.

### P&C Intelligence

The entire event layer now passes through a strict Intelligence gate before pages render it. It includes:

- war / conflict / attacks
- maritime security / piracy / seizures
- fraud / crime
- smuggling / trafficking / interdictions
- labour / civil unrest
- weather / natural hazards
- groundings / collisions / casualties
- infrastructure / transport disruption
- cyber
- sanctions / enforcement

Routine corporate development is excluded from P&C Intelligence.

### Governance

`data/11_systems_waterways_governance.xlsx` has been patched to map current canonical port IDs for:

- Busan → Busan Port Authority
- Port of Busan → Busan Port Authority
- Port of Incheon → Incheon Port Authority
- Port of Gwangyang → Yeosu Gwangyang Port Authority

SQL `004_governance_and_cleanup.sql` repeats the Korean authority backfill idempotently after normalization.

## Migration-night sequence

### 1. Create Supabase project

Create the project and copy:

- Project URL
- anon key
- service role key

Do **not** expose the service-role key in browser/client code. Streamlit stores it server-side in app secrets.

### 2. Run SQL in this order

In Supabase SQL Editor:

```text
sql/001_core_platform.sql
sql/002_rls_and_auth.sql
sql/003_product_views.sql
sql/007_auth_profile_trigger.sql
```

Do not run the cleanup/routing SQL until data has been normalized.

### 3. Set local environment variables

```bash
export SUPABASE_URL="https://YOUR_PROJECT.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="..."
```

### 4. Mirror the current workbooks into Supabase

From the kit root:

```bash
python scripts/seed_legacy_from_excel.py --data-dir data --truncate
```

This creates the exact workbook/sheet-shaped mirror used by the combo apps.

### 5. Normalize the core model

```bash
python scripts/normalize_core.py
```

This currently normalizes the highest-value layers first:

- sources
- companies/entities
- company relationships
- ports
- infrastructure assets
- dry ports
- economic zones
- vessels/mobile assets
- events
- event locations
- event links
- impact chains
- port governance
- infrastructure transactions
- sanctions designations

The untouched workbook sheets remain available through `pc_legacy_sheet_rows`, so no client coverage is lost while we normalize the remaining domains.

### 6. Apply governance + event routing

Run in SQL Editor:

```text
sql/004_governance_and_cleanup.sql
sql/005_event_routing.sql
```

`005_event_routing.sql` is the database-level equivalent of the new product rules:

- security/disruption → Intelligence
- security/disruption with commercial impact → Trade Alerts
- corporate → Trade only
- corporate → never Intelligence unless modeled as a separate disruption/security event

### 7. Run quality checks

```bash
python scripts/cleanup_validate.py
python scripts/verify_migration.py
```

Then run:

```text
sql/006_validation.sql
```

The key check is:

```text
intelligence_corporate_leakage = 0
```

### 8. Switch the client apps to Supabase

In Streamlit secrets:

```toml
PC_DATA_BACKEND = "supabase"
PC_SUPABASE_NO_FALLBACK = "false"
PC_REQUIRE_AUTH = "false"

[supabase]
url = "..."
anon_key = "..."
service_role_key = "..."
```

Deploy Trade and Intelligence and verify the pages against Supabase.

Leave Excel fallback enabled on the first migration night. Once verified:

```toml
PC_SUPABASE_NO_FALLBACK = "true"
```

### 9. Enable client authentication

Create your own user in Supabase Authentication, then run:

```bash
python scripts/bootstrap_super_admin.py your@email.com
```

Use `pc-power-admin.py` to create organizations, seat limits, memberships and product entitlements.

Then change each client app:

```toml
PC_REQUIRE_AUTH = "true"
```

## Client/tenant model

Each client — e.g. AD Ports, DP World, Brookfield — gets one `pc_organizations` row.

P&C controls:

- seat limit
- active/suspended status
- Trade entitlement
- Intelligence entitlement
- NERAI entitlement
- tier
- AI limits
- feature overrides

User roles:

- `org_admin`
- `senior_analyst`
- `analyst`
- `executive`
- `viewer`

The shared client-admin app lets the client's `org_admin` view their users/products and submit invite/role/access requests. **P&C Power Admin retains final commercial and seat control.**

## Client workspace

The database already includes tenant-isolated tables for:

- saved queries
- saved watchlists
- watchlist items
- AI sessions/messages
- scenarios
- client notes
- client administration requests

Trade Search and Intelligence Search already expose **Save query to my workspace** once authenticated.

## AI Admin model

`pc-power-admin.py` includes an AI Research & Enrichment workspace. The optional `shared/pc_ai.py` uses OpenAI's Responses API and can use web search, but the result is written only to `pc_staged_records` for review. It never writes AI research directly to canonical production tables.

This is the intended pipeline:

```text
source / query
→ AI research & extraction
→ staged record
→ validation
→ analyst review
→ canonical database
```

Examples after the foundation is running:

```text
Research all African ports and propose missing records.
Load current CMA CGM, Evergreen and Matson fleets.
Research Brookfield transport/logistics acquisitions from 2016–2026.
Ingest and enrich UKMTO incidents for the last decade.
Fill missing IMO/operator/owner fields on incomplete vessels.
```

## Important security note

During migration, `PC_REQUIRE_AUTH=false` is acceptable for local/private testing only. Before public client use:

1. configure Supabase Auth;
2. create organizations and entitlements;
3. set `PC_REQUIRE_AUTH=true`;
4. keep the service role key only in server-side Streamlit secrets.

## Files

```text
app.py
pc-intelligence.py
pc_intelligence_app.py
pc-nerai.py
pc-power-admin.py
pc-client-admin.py
shared/
scripts/
sql/
data/
.streamlit/
requirements.txt
```

## Combined Trade + Intelligence client app

`pc-combined.py` is the single Streamlit deployment for clients licensed for both base products. It presents a product switcher and runs the existing `app.py` or `pc-intelligence.py` source, so the two base applications remain independently maintainable while using the same Supabase data model.

Deploy it as a separate Streamlit app with main file `pc-combined.py`. Deep links support `?product=trade` and `?product=intelligence`. Product entitlements remain enforced by the shared authentication layer once `PC_REQUIRE_AUTH=true`.

## Market-intelligence addition: The Signal Group

The Trade product now includes a normalized **Freight & Commodity Markets** workspace. The initial public-source backfill is designed around The Signal Group Weekly Market Monitor archive (dry bulk, tanker, and later commodity radars).

Run `sql/008_market_intelligence.sql` after the core schema. It creates attributed market-report and observation tables plus Trade client views. Market observations are **pending and non-client-visible by default** until approved in `pc-power-admin.py`.

Quick test seed:

```bash
python scripts/seed_market_sample.py
```

2026 archive research/backfill:

```bash
python scripts/ingest_signal_group.py --year 2026 --families dry,tanker --weeks 1-36
```

The crawler only uses publicly accessible pages, does not bypass authentication/paywalls, stores normalized facts and attribution rather than copies of article text, and uses OpenAI extraction only when `OPENAI_API_KEY` is configured. Values visible only in chart images are not accepted unless separately researched/verified.

The schema supports freight rates, indices, fleet/tonnage supply, supply-demand conditions, commodity flows, port/congestion conditions, asset values and P&C market signals. This lets future sources (Baltic, PortWatch, commercial APIs, commodity feeds) sit beside Signal in the same model.

## Global Trade-System Expansion (v3.2)

The Trade product now has a normalized expansion layer for the broader economic system described in the P&C model: energy infrastructure, industrial production, physical trade flows, market instruments, port economics, inland transport, chokepoints and country macro context.

Run after SQL 008:

```text
sql/009_trade_system_expansion.sql
```

Then seed the source/licensing registry and map the data already present in the current workbooks:

```bash
python scripts/seed_open_source_registry.py
python scripts/normalize_trade_expansion.py
```

The expansion adds:

- `pc_observations` — mandatory provenance/methodology/licence record for imported or derived datapoints
- `pc_energy_assets` + `pc_energy_asset_connections`
- `pc_industrial_assets`
- `pc_logistics_facilities`
- `pc_market_instruments` + `pc_market_prices` + `pc_market_exposure_links`
- `pc_trade_flows`
- `pc_supply_series`
- `pc_port_metrics` + `pc_port_capabilities`
- `pc_transport_routes` + `pc_transport_route_status`
- `pc_chokepoints` + `pc_chokepoint_status`
- `pc_macro_indicators`

Canonical identity stays in `pc_entities` / `pc_assets`; these tables extend those records rather than creating duplicate Jazan, Busan, refinery, port, mine or company identities.

### New Trade client workspaces

`app.py` now exposes:

- **Energy & Industry**
- **Market Instruments**
- **Trade Flows & Supply**
- **Country & Macro**

alongside the existing Freight & Commodity Markets page. These read the normalized Supabase expansion tables. The combined client app automatically inherits the same additions because it runs the Trade app code.

### P&C Power Admin

`pc-power-admin.py` now includes **Trade System Builder**, with campaign examples for:

- African ports and connectivity
- GCC / Red Sea refineries
- Brookfield / OMERS / Macquarie transport investment histories
- global mines and export chains
- logistics parks, free zones and inland terminals

All AI research still stages proposed changes for review rather than writing directly into canonical production tables.

### Source/licensing discipline

`data_seed/open_source_registry.csv` seeds the initial open/free source universe (EIA, JODI, Global Energy Monitor, Energy Institute, IMF, World Bank, UNCTAD, WTO, UN Comtrade, FAOSTAT, SEC EDGAR, OpenStreetMap, OurAirports and The Signal Group). Treat the registry as a starting point only: redistribution rights are stored and should be verified at dataset/series level before client-facing display.

### Immediate usable ingestion helpers

After SQL 009:

```bash
python scripts/seed_market_instruments.py
python scripts/ingest_world_bank_macro.py --start 2016
python scripts/stage_ourairports.py
```

`stage_ourairports.py` deliberately stages airport infrastructure for review instead of writing directly into canonical assets. `ingest_world_bank_macro.py` writes official World Bank macro observations with source attribution. `seed_market_instruments.py` creates the initial canonical benchmark objects (Brent, WTI, Henry Hub, gold, copper, iron ore, wheat, corn, soybeans, TD3C and BDI) so asset/company exposure relationships can be built even before price-series ingestion is connected.
