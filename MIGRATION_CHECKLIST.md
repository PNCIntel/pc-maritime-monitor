# Migration checklist

- [ ] Create Supabase project
- [ ] Run SQL 001
- [ ] Run SQL 002
- [ ] Run SQL 003
- [ ] Run SQL 007
- [ ] Set local SUPABASE_URL + service role key
- [ ] Run `seed_legacy_from_excel.py --data-dir data --truncate`
- [ ] Confirm `pc_legacy_sheet_rows` populated
- [ ] Run `normalize_core.py`
- [ ] Run SQL 004
- [ ] Run SQL 005
- [ ] Run `cleanup_validate.py`
- [ ] Run `verify_migration.py`
- [ ] Run SQL 006 validation
- [ ] Confirm Intelligence corporate leakage = 0
- [ ] Confirm Busan governance mapping appears
- [ ] Set Streamlit `PC_DATA_BACKEND=supabase`
- [ ] Keep Excel fallback on for first verification
- [ ] Deploy Trade
- [ ] Deploy Intelligence
- [ ] Verify Trade Alerts & Disruptions
- [ ] Verify Intelligence excludes routine corporate development
- [ ] Create Supabase Auth super-admin user
- [ ] Run `bootstrap_super_admin.py`
- [ ] Create first client organization in Power Admin
- [ ] Assign seat limit + product entitlements
- [ ] Deploy Client Admin
- [ ] Deploy NERAI scaffold
- [ ] Turn `PC_REQUIRE_AUTH=true` on client apps
- [ ] After stable verification, set `PC_SUPABASE_NO_FALLBACK=true`

- [ ] Deploy `pc-combined.py` for clients entitled to both P&C Trade and P&C Intelligence.

## Market layer
- [ ] Run `sql/008_market_intelligence.sql`
- [ ] Run `python scripts/seed_market_sample.py` for the initial attributed Signal test data
- [ ] Open **Power Admin → Market Data** and approve test observations
- [ ] Confirm **Trade → Freight & Commodity Markets** displays approved observations
- [ ] Optional: run `python scripts/ingest_signal_group.py --year 2026 --families dry,tanker --weeks 1-36`
- [ ] Review AI-extracted market observations before making them client-visible

## Global Trade-System expansion
- [ ] Run `sql/009_trade_system_expansion.sql`
- [ ] Run `python scripts/seed_open_source_registry.py`
- [ ] Run `python scripts/normalize_trade_expansion.py`
- [ ] Open **Power Admin → Trade System Builder** and verify expansion-table counts
- [ ] Verify **Trade → Energy & Industry**
- [ ] Verify **Trade → Market Instruments**
- [ ] Verify **Trade → Trade Flows & Supply**
- [ ] Verify **Trade → Country & Macro**
- [ ] Confirm provenance/source/licence fields are retained for new imported datasets
- [ ] Do not enable client-facing redistribution of any series until its source rights are verified
- [ ] Run `python scripts/seed_market_instruments.py`
- [ ] Optional first macro load: `python scripts/ingest_world_bank_macro.py --start 2016`
- [ ] Optional airport staging: `python scripts/stage_ourairports.py`
