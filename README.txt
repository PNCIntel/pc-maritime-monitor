P&C Trade System v3.3.35 - Live Canonical Commercial Bridge

Replace:
  app.py
  shared/pc_trade_system.py

Changes:
- pc_transactions now feeds Transactions V125, Infra Deals, Investments, commercial search/homepage.
- pc_trade_flows remains direct from Supabase and now resolves readable origin/destination names.
- pc_observations query corrected to current schema (removed nonexistent record_status).
- energy/industrial pages now use canonical pc_energy_assets and pc_industrial_assets.
- specialization rows join back to pc_assets for names/country/location.
- existing live canonical entities/assets/relationships/events/vessels bridge retained.

No Excel rebuild is required for newly canonicalized records.
