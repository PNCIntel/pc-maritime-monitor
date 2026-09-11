# P&C Population + AI Bundle

Copy these files into the existing `pc-maritime-monitor` repository, preserving folders.

## Streamlit secrets

Add:

```toml
OPENAI_API_KEY = "YOUR_OPENAI_API_KEY"
OPENAI_MODEL = "gpt-5.6-luna"
```

Keep the existing Supabase secrets as well.

## Recommended sequence

First deterministic population:

```bash
python scripts/seed_open_source_registry.py
python scripts/seed_market_instruments.py
python scripts/ingest_world_bank_macro.py --start 2016
python scripts/seed_chokepoints.py
python scripts/ingest_portwatch.py
python scripts/verify_migration.py
```

Or:

```bash
python scripts/run_population.py
```

Optional staging:

```bash
python scripts/stage_ourairports.py
```

Optional Signal Group backfill:

```bash
python scripts/ingest_signal_group.py --year 2026 --families dry,tanker --weeks 1-36
```

## AI research

AI research never writes directly to canonical production tables. It stages proposals in
`pc_staged_records` for review in `pc-power-admin.py`.

Examples:

```bash
python scripts/ai_research_stage.py --campaign african_ports
python scripts/ai_research_stage.py --campaign gcc_refineries
python scripts/ai_research_stage.py --campaign mines_export_chains
python scripts/ai_research_stage.py --campaign logistics_parks
python scripts/ai_research_stage.py --campaign infra_investors
```

Then deploy/open `pc-power-admin.py` and use the Review Queue.

## PortWatch

`ingest_portwatch.py` populates `pc_observations` and `pc_port_metrics` for canonical ports
that can be matched conservatively by name/country. Unmatched ports are written to
`external_data/portwatch_unmatched.json` for review.

## Chokepoints

`seed_chokepoints.py` creates identity/geography baseline records only. It does not invent
capacities or live status. Those should be populated separately from attributed sources.
