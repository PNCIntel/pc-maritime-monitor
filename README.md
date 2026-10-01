# P&C Research-First Analyst Loader v3.4 — Validate & Replay

This is a targeted update to v3.3.

## What changed

1. **Deterministic graph validation gate** (`pc_graph_validator.py`)
   - Runs after research/graph synthesis and before database mapping.
   - Makes no web/OpenAI calls.
   - Normalizes invalid/`unknown` dates to NULL.
   - Holds invalid vessel IMO identities.
   - Prevents former vessel names from becoming separate physical ships.
   - Holds combined roles such as `owner/operator` or `charterer/operator` instead of guessing.
   - Converts charter transactions into charter relationships.
   - Removes inferred ownership end dates when they merely coincide with a charter/operator start.
   - Keeps journalists/commentators out of the operational people graph.
   - Neutralizes uncertain security-event titles/descriptions and keeps attribution/personnel effects in claims.
   - Holds acquisition/sale transactions with no identified buyer or seller.

2. **Replay saved research dossier in Power Admin**
   - Upload a previously downloaded research dossier JSON.
   - See automatic repairs, held findings and excluded context.
   - Download/copy the validated dossier.
   - Build a queueable package with one analyst approval.
   - No OpenAI/web-research call is made during replay.

3. **Connected replay without re-research**
   - After core publication, a validated vessel dossier seeds the connected-review stage directly.
   - The analyst sees the saved vessel history and relationships for approval.
   - No additional AI/web research call is made for the replayed connected plan.

4. **Vessel replay publication**
   - Publishes vessel identity history.
   - Resolves/creates evidence-backed connected companies through existing resolver RPCs.
   - Writes evidence-backed entity ↔ mobile-asset relationships.
   - Vessel transactions remain held until the `pc_transactions` asset-target mapping is verified; they are not silently forced into a company transaction schema.

## St Helena regression test

Fixture: the saved TWZ St Helena research dossier.

Local results:
- automatic repairs: 5
- held findings: 2
- excluded non-operational context: 2
- queueable core proposals: 7
- canonical vessel proposal uses IMO 8716306
- `MNG Tahiti` remains vessel name history
- event title becomes `Projectile strike on M/V St. Helena in Strait of Hormuz`
- unconfirmed attack attribution/personnel effects are removed from the factual event description
- MNG Maritime ownership end date inferred from Extreme E charter start is cleared
- Extreme E charter is converted from a transaction to a relationship

## Deploy

Replace/add these files from this package in the same application repository:
- `pc-power-admin.py`
- `pc_graph_validator.py` (new)
- `pc_research_dossier.py`
- `pc_connected_research.py`
- `pc_intelligence_pipeline.py`

The package also includes the supporting v3.3 files unchanged for consistency.

## Test in staging

1. Open **Load intelligence**.
2. Scroll to **Validate / replay saved research dossier**.
3. Upload the downloaded St Helena dossier JSON.
4. Review the validation report.
5. Tick the approval checkbox and click **Build package from validated dossier**.
6. Click **Queue all extracted records**.
7. Run **Research, resolve & POPULATE DATABASE**.
8. Core publication should run normally.
9. The pipeline should go directly to **Review connected findings** for the replayed St Helena vessel rather than running a new OpenAI research pass.
10. Review and approve connected enrichment.

## Important limitation

The code deliberately holds vessel transaction rows because the exact asset-target mapping for `pc_transactions` has not yet been verified against the live database. Vessel identity history and evidence-backed company↔vessel relationships are handled in this version.

This package passed Python compile checks and the St Helena validator regression test locally. It has not been executed against the live Supabase instance.
