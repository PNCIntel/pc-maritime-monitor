# P&C Core Intelligence Model v3.0 — Seed / Supabase Rehearsal

This package is a controlled sample migration of the current P&C model into a normalized PostgreSQL/Supabase-ready structure.

## Core design
There is one canonical data layer. P&C Trade System and P&C Intelligence are separate product views over the same entities, assets, vessels, events, relationships, financials and source evidence.

No security-data fork is created.

## Included
- `schema/001_core_schema.sql` — PostgreSQL/Supabase DDL and initial product views.
- `schema/002_seed_load_psql.sql` — psql CSV seed loader.
- `seed/*.csv` — relationship-dense sample data covering all 11 model layers.
- `tests/model_validation_queries.sql` — 15 validation queries.
- `tests/VALIDATION_QUESTIONS.md` — human-readable acceptance tests.
- `docs/PC_Core_Intelligence_Model_v3_0_Seed.xlsx` — readable workbook view of the seed.
- `docs/MODEL_MAP.md` — architecture and migration notes.

## Sample cases
- AD Ports Group: canonical company, Tbilisi Dry Port, Khalifa Port, investments, financial metrics and ADPORTS market history.
- Gulftainer: company + Al Dhaid multimodal corridor / investment.
- PGSA: Mraweh, Tarif, GasLog Shanghai and Al Rekayyat; direct designations and secondary STS exposure.
- MARSEC: official-source seed cases from Japan Coast Guard, Korea Coast Guard and Indian Coast Guard.
- Security / disruption: port strike, typhoon, drone/port attack, port explosion and vessel attack.
- Infrastructure: Genoa and Morebaya development events.

## Data quality
`verified` means the seed row is grounded in the current model/source record.
`provisional` means the relationship or identity is usable for schema testing but should be reverified against a stronger registry or primary maritime source before production.
No synthetic intelligence events are included.

## Supabase migration order
1. Run `schema/001_core_schema.sql`.
2. Load `11_sources_observations.csv` first.
3. Load entities, assets and mobile assets.
4. Load relationships and geographies.
5. Load events and event links.
6. Load security/compliance, finance, market data and intelligence analysis.
7. Run `tests/model_validation_queries.sql`.
8. Expand from the full v2.9 dataset only after the validation set passes.

## Front-end rule
Database IDs remain stable internal keys. Streamlit should display `name`, human-readable relationship labels and linked entity names, not raw IDs.
