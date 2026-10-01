# P&C Research-First Analyst Loader v3

Purpose: fix the failure mode where a source is forced into database tables before the AI has understood and researched the real-world story.

## What changes

The Load intelligence intake now uses this order for AI web research:

1. Read the supplied article/report text.
2. Broad web investigation of the real-world subject, without mentioning database tables or IDs.
3. Generate up to 7 material unanswered research questions (identity/history/ownership/operator/transaction status/attribution).
4. Run one bundled follow-up web investigation for those questions.
5. Synthesize one real-world graph: companies, people, vessels/assets, vessel identity history, events, transactions, relationships, projects, contracts, claims, timeline, and research gaps.
6. Deterministically map only the graph's core objects to the existing P&C proposal tables.
7. Send those proposals through the existing v0.7 queue, identity resolver, research, canonical publisher, graph sync and v2 connected-enrichment stages.

The analyst does not see or enter database IDs.

## Files

- `pc-power-admin.py` — modified intake path and research dossier review/download UI.
- `pc_research_dossier.py` — new research-first investigator and deterministic core mapper.
- Existing v2 files are included unchanged except where already modified in v2.

## Important guardrails

- A former vessel name does not create a second physical vessel.
- Valid IMO values must be exactly 7 digits before they are placed on a proposal.
- Abstract fleets, leadership groups, and regional commercial teams are not physical assets.
- Announced/pending transactions are not silently converted into completed ownership.
- Allegations and disputed attribution remain qualified claims.
- The research dossier preserves connected findings for downstream specialist publication.

## API cost / bounded behaviour

For each text URL/report in `AI web research + extraction` mode, v3 normally performs:

- 1 broad OpenAI web-search call
- 1 small JSON call to identify remaining research questions
- 0 or 1 bundled follow-up OpenAI web-search call
- 1 JSON graph-synthesis call

This is intentionally bounded for batches such as 10 articles; it does not launch one API call per discovered entity.

## Deployment

Replace the current v2 files with the files in this ZIP, including the new `pc_research_dossier.py`. No SQL migration is required by this patch.

Deploy to staging first.

## First acceptance test — TWZ St Helena

Load only:

`https://www.twz.com/news-features/claims-swirl-around-u-s-marines-injured-aboard-mystery-vessel-attacked-in-the-strait-of-hormuz`

Use `AI web research + extraction`.

Before queuing, open **Research dossiers — inspect / copy / download**.

The dossier should, where supported by evidence, identify:

- one physical vessel anchored by IMO 8716306
- St Helena / MNG Tahiti as identity history, not two ships
- MNG Maritime as a connected company with its role kept distinct from legal ownership unless verified
- the Hormuz incident as an event
- unconfirmed/attributed claims kept qualified
- research gaps such as unresolved current ownership if not verified

Then queue and run `Research, resolve & POPULATE DATABASE`.

Success is not staging alone. Check that the canonical vessel/company/event records and connected history are published or explicitly held with a reason.

## Regression tests performed locally

`pytest -q test_research_dossier.py test_connected_research.py`

Result: 6 passed.

Python compile checks also passed for the modified/new files.

## Known limitation

The source-level dossier and graph are now research-first, but final specialist publication still relies on the existing v2 connected publisher. If the dossier is correct but a specialist relationship/history does not reach its table, the remaining defect is in that publisher, not in source understanding. The dossier download makes that boundary visible for debugging.

## v3.2 source retrieval hotfix
- Public URL intake no longer depends on Jina availability.
- Tries publisher page directly first, then Jina.
- HTTP 429/403/reader failures no longer discard the source; URL-only research seed proceeds to OpenAI web research.
- Empty proposal sets are reported as research/extraction failures rather than misleading Supabase snapshot errors.
