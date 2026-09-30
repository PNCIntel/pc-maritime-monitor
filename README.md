# P&C Power Admin — Svitzer company-depth controlled test

## What this package does
Adds an **analyst-facing Company research (controlled test)** page to the existing Power Admin, alongside its existing intelligence/document loaders. This is a bounded company-depth research/publishing trial for the **existing canonical Svitzer company**.

The page takes an official homepage, fetches relevant same-domain official subpages using the same consented public Jina reader principle, sends retrieved text to the configured OpenAI API, persists an evidence-linked research review in the existing `pc_ingestion_jobs` table, and presents a preview for analyst approval. Upon approval it resolves one **unique exact existing company identity**, updates `pc_company_profiles` without destroying existing populated fields, and inserts *individually approved, provenance-tagged* offices and management/leadership people/roles. It re-checks the profile through Supabase before marking that **subset** complete.

**No SQL migration** is needed for this bounded trial: the supplied schema already contains these tables and fields. No raw SQL/IDs are required from the analyst.

## IMPORTANT: what this package does NOT do
This is **not yet the complete universal loader**. The new page **does not** publish related subsidiary/acquisition relationships, vessel objects, vessel historical identity, contracts, full fleet discovery, regulatory milestones or dashboard routing. These candidates are saved in its review job and explicitly counted as HELD. Do not mistake `completed_profile_only` (or `partial`) for a completed company import. It does not remove previous wrongly created `Svitzer Fleet`/`Svitzer Regional Commercial Teams` records, or update your Trade and Intelligence readers. Existing main intake and the Phase 1 research/reconciliation pipeline are preserved.

A source-grounded extraction with a URL is **not** independent verification of a person's appointment, legal ownership or a vessel IMO. Analyst review is required for each published office/leadership role. Missing web pages appear as errors and fewer than two retrieved pages block the deep-research test. Jina and OpenAI receive only consented public sources; do not put confidential reports in this company mode.

## Deployment (STAGING)
1. Back up the deployed files. Copy `pc-power-admin.py` to your repo's existing Power Admin main file **using its configured filename**, `pc_intelligence_pipeline.py`, `pc_company_depth.py`, and `pc_company_source_reader.py` to the same repo directory (alongside the existing helper modules). The included Power Admin file is based on the previous Phase 1 patched version, not on unknown subsequent production changes; compare before replacing if you've made further edits.
2. Retain your existing `shared/`, `pc_v07_core.py`, `pc_v15_bulk_replay.py`, `pc_v16_research.py`, `pc_document_loader.py`, `pc_newsletter_pdf.py`, other existing module dependencies and environment secrets; do not replace them with earlier copies.
3. Deploy only to STAGING first and confirm the existing Power Admin boots. If you did not previously deploy Phase 1, deploy the included pipeline together with the main file.

## The Svitzer test
1. Choose **Research company (controlled test)** in the sidebar. Enter `Svitzer` and `https://svitzer.com/`.
2. Check the consent box. Click **Research company and linked pages**. The expected output is an actual count of retrieved official pages, any retrieval errors, and a saved persistent review job. If it only retrieves the homepage, add official leadership/contact links manually; don't approve.
3. Open the saved review. Inspect JSON *especially source URLs*, proposed headquarters, leadership roles, candidate vessels, related companies, missing fields and retrieval errors. If fields are absent, this test has NOT established their completeness.
4. Select only office and leadership rows you can validate from the official cited page. Approve the profile and click **Publish verified profile and selected offices**. The web research review remains saved; vessel/ownership/contract information remains held.
5. Check the summary for `profile_updated`, `offices_added`, `people_added`, `unresolved_count`; check the existing Svitzer company in Trade only to the extent that the Trade reader actually reads these specialist tables. Do not interpret lack of Trade visibility as absence in the DB: the existing dashboard readers still need separate repair.
6. Run again with the same sources only when testing idempotency. Do NOT requeue the old three-record `Svitzer Fleet` extraction.

## Automated local tests
```
python -m unittest -v test_company_depth.py
python -m py_compile pc-power-admin.py pc_company_depth.py pc_company_source_reader.py pc_intelligence_pipeline.py
```
The tests exercise same-site discovery boundaries, URL provenance, malformed IMO holds, wrong-type canonical rejection, specialist profile/office writes and held fleet candidates with fake Supabase responses. They do **not** simulate live OpenAI/Jina/Supabase/Streamlit or prove full research completeness. Stop/revert if staging fails.
