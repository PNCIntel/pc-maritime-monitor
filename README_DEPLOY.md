# Power & Corridors Universal Loader v0.7 — Bulk staging + Trade preview

**Release type:** Additive, review-stage only. Nothing in this package automatically writes to canonical `pc_entities`, `pc_assets`, `pc_mobile_assets`, `pc_events`, event links, routes, corridors, or client-visible Trade tables. Run migrations against a staging Supabase project first and retain a backup of your current GitHub entrypoint.

## What is included

- `pc-power-admin.py`: your existing v0.6.1 research workspace plus a fast Bulk Queue page and a Trade Preview, with the white design preserved.
- `pc_v07_admin_panel.py`: import XLSX/CSV/JSON (including prior staging-proposal exports), inspect first 25 records, queue thousands without per-row AI, and browse job progress 50 at a time.
- `pc_v07_core.py`: transport-safe source data, dedupe fingerprints, batched identity resolution, and extraction of source-provided analysis.
- `pc_bulk_worker.py`: independent bounded persistent worker. Grouped Supabase lookups, 100-row staging inserts, retry-safe sidecars, and optional *bounded* research queues. **No canonical writes.**
- `pc_trade_intelligence.py`: read-only Trade developments, companies, assets, corridors, draft assessments and linked references. Staged drafts are shown only with `admin=True`.
- `pc_trade_preview.py`: a separate authenticated administrator-only Streamlit entrypoint for Trade preview. Point a temporary second Streamlit app at this file to explore your live canonical records and unpublished pipeline.
- `01_SUPABASE_V07.sql`: additive queue, source observations, versioned draft event assessments, research cache/tasks, row-leasing RPCs and supporting indexes.
- `.github/workflows/pc-bulk-worker.yml`: GitHub Actions job that runs at most one instance on a five-minute schedule, plus manual dispatch.
- `pc_bulk_requirements.txt`: minimal worker dependency set.
- `test_v07_local.py`: source-workbook and 229-row regression tests using an in-memory mock database (no credentials or production writes).

## Deployment — do these in order

1. **Backup your current Power Admin script and database schema.** Run `01_SUPABASE_V07.sql` in a test Supabase project, inspect all warnings, then run on the live project at a suitable maintenance time. The existing-table indexes can briefly lock writes during creation on large installations. The script makes no canonical data changes.
2. Copy `pc-power-admin.py`, `pc_v07_admin_panel.py`, `pc_v07_core.py`, `pc_trade_intelligence.py` into the same GitHub directory as your existing Power Admin entrypoint. **Keep the actual entrypoint filename (`pc-power-admin.py`) unchanged.** Your `shared/pc_auth.py` is untouched.
3. Copy `pc_bulk_worker.py` and `pc_bulk_requirements.txt` into your repository root and `.github/workflows/pc-bulk-worker.yml` to **exactly** that workflow path. The workflow assumes these two worker files are at repository root. If your project uses a subdirectory, update the workflow's `pip` and `python` paths.
4. In **GitHub → Settings → Secrets and variables → Actions**, add `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`. Never commit secrets or send these values in chat. Optional: add `OPENAI_API_KEY`. Your Streamlit secrets remain where they are, separately, for the admin application.
5. Deploy Power Admin from `pc-power-admin.py`. In the sidebar select **Bulk queue (fast)**, upload `PC_ANALYTICAL_MULTIMODAL_MASTER_28_EVENTS_20260925(3).xlsx` or select the current extracted package, and click **Queue complete package**. The job is stored in Supabase and survives closing the browser.
6. Open **GitHub → Actions → P&C batch staging worker → Run workflow** once to verify it processes the first 100–800 rows. Scheduled runs then process pending rows, subject to GitHub Actions scheduling and quotas. Review the queue page for counts and errors.
7. Choose **Trade preview** inside Power Admin. It reads existing canonical Trade records immediately. After the worker stages the batch, use the **Review pipeline** tab to inspect the 28-event workbook and its draft assessments, including what happened, why it matters, commercial implications, P&C assessment and monitoring indicators.
8. Optionally deploy `pc_trade_preview.py` as a **second, admin-only Streamlit app** to show Trade records without opening Power Admin. To add the page to your actual Trade application, import `render_trade_intelligence` from `pc_trade_intelligence` and call it after that application's **own** successful authentication, with `admin=False` for client views. Configure proper tenant-aware access/RLS before exposing any client-facing route.

## Optional persistent AI research

Selecting “Queue targeted AI research” in Power Admin creates research tasks for unresolved companies, physical assets, vessels and corridors; it **does not** research every news item or every relationship. The GitHub workflow ships with `PC_ENABLE_AI_RESEARCH: '0'` so no unexpected API spend occurs. Set it to `'1'` and configure `OPENAI_API_KEY` **only when ready**. The worker processes at most 3 web-research tasks per scheduled run and caches findings as **unverified leads**. AI output never changes a canonical company ID or designation automatically.

Existing URL/PDF/multi-source AI extraction remains under **Research & review (existing)**. Queue the resulting extracted package in **Bulk queue (fast)**; heavy work runs separately. An independently deployed GitHub Actions worker will not continue if the Actions workflow is disabled, secrets are missing, or your plan's Action quota is exhausted.

## Trade-facing content rules

- **Canonical**: the existing `pc_events`, companies, assets, links and corridors. The admin preview shows all canonical statuses; the client helper filters event `trade_visible = true` and verified asset records. Your Trade application's RLS and existing tenant permissions must still be enforced by its own backend.
- **Draft**: `pc_staged_records`, `pc_v07_event_assessments`, `pc_v07_research_cache` and source observations. These are available **only** in admin review. A staged event does not become a client-visible event merely because the worker has completed.
- **Analysis**: the loader preserves `ALL_EVENT_ANALYSIS` sheet fields by Event ID, or existing event `metadata.event_summary`, `metadata.why_it_matters`, `metadata.commercial_implications`, `metadata.assessment` and `metadata.monitoring_indicators`. It does not invent missing assessments when no supporting information is provided.
- **Corridors**: proposals remain unresolved until constituent routes and connections are verified. No inferred impact from mere geographical proximity.

## Scale / known remaining work

The local mock regression processes 229 supplied review proposals, generates 60 draft event assessments and preserves all 70 event links, then confirms safe retries. A 10,000-row test covers **in-memory preparation only**, not network speed. The real processing rate depends on Supabase latency, plan quotas, payload sizes and GitHub Actions. The first production measurement should be **time per 1,000 queued, matched and staged rows**, plus initial Trade preview page load latency.

**Not yet implemented:** automatic canonical publishing/transactional apply and rollback; source-backed event deduplication against all canonical events; final propagation of newly created IDs into graph links; automatic event-to-corridor impact ratings; AI analysis of articles lacking supplied analytical text. These remain explicit analyst review states and must not be presented as done.

## Troubleshooting

- `pc_v07_queue` missing: migration wasn't applied to the same Supabase project the app is using.
- Queue never drains: check GitHub Actions is enabled, workflow on default branch, and both Actions secrets exist; run workflow manually to inspect errors.
- `permission denied` in worker: use the server-side **service-role key** in GitHub Actions; never use anon key for this privileged job.
- All identities appear NEW: match failures must raise rather than returning an empty registry; worker explicitly retries a failed lookup and never treats the failure as proof of novelty.
- Staged draft assessments missing: worker must process the v0.7 queue; older v0.6 jobs are not retroactively backfilled by this release.
