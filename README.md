# P&C Analyst Loader v3.6.1 — source graph publication

Replace the corresponding files in the existing Power Admin repository and reboot Streamlit. Confirm **Loader build v3.6.1** before importing the batch.

This patch publishes saved source-backed company/infrastructure relationships, event links, transactions, project details and contracts after their core records have canonical publication IDs. Missing or ambiguous endpoints and database constraint errors stay visible as holds. Company and physical-asset names can coincide: endpoint types disambiguate them. Transaction values preserve their basis, and future projects remain planned. Vessel relationship history retains its source finding and qualification. Replay refreshes saved research without calling AI again.

## Nine researched articles

`production_batch_9/NINE_ARTICLES_RESEARCHED_PROPOSALS.json` contains 63 core proposals for the existing **Load intelligence → Universal intake** structured-file input. It carries the per-source graph findings for the connected publisher. These are researched proposals, not production publication results. Existing canonical records should match rather than duplicate.

Upload that JSON, prepare the package, review identity matches, then apply/reconcile canonical records and publish connected enrichment through the existing workflow. `NINE_ARTICLES_SOURCE_GRAPHS.json` is the readable research trail; do not upload it as a replacement for the structured proposals. The KSIE original page was unavailable, so its facts cite alternative reporting explicitly. Uncertain St Helena involvement stays qualified. No aircraft identity is inferred from a model number.

Run `VERIFY_AFTER_LOAD.sql` with the returned job UUID. It checks core publication through staging and returns connected records. Refresh both Trade and Intelligence apps, then inspect companies, ports/terminals, vessels, events and Deals, Projects & Contracts. Check CLI closing on 1 October, its 2 October announcement and USD 835 million enterprise value; KEZAD facility remains planned for 2028; Pacific Link remains proposed. Confirm company and asset records called Port of Tauranga are linked with their correct types.

## Verification performed

58 loader unittest checks, 8 article-context checks and 5 additional function checks passed (71 total). Coverage includes document reuse and company jobs, company publication and retry, held roots, typed endpoints, unpublished identities, partial failures, transaction value mapping and source context isolation. Python compilation passed.

An offline publisher check of the curated batch produced 11 company/infrastructure relationships, 26 event links, 1 transaction, 8 project details and 1 contract with no unresolved endpoints. Existing vessel replay handles vessel relationships and history separately. This check used resolved test IDs and a database double: it does not validate Supabase constraints or prove production writes.

## Current deployment blocker

The supplied Trade and Intelligence apps loaded successfully. Their UI exposes read/analysis controls and directs writes through Power Admin. No current Power Admin URL, repository/deployment connection or configured database credentials is available in this workspace. This patch is not deployed and the nine articles have not been verified as loaded in production. Newsletter cleanup has not been executed.


This is a replacement-file patch for the existing P&C application repository.
It is not a standalone application or a database migration.

## Multi-source intake changes in v3.6.1

This updates the existing **Load intelligence → Universal intake** screen. Enter
up to 20 article URLs and add PDF, DOCX, TXT/MD newsletters or structured files to
one package. Printed newsletters are extraction sources; this intake does not
insert them into `pc_documents`. The separate **Load documents** screen still
stores documents as reports/evidence.

- Merged company/vessel/event proposals retain non-recursive original per-source
  proposals. Connected review reconstructs each source separately instead of
  assigning one article's claims or relationships to another article.
- Ambiguous in-batch or existing-event candidates receive a canonical hold in
  staging. Independent records continue through enqueue/publication. Database
  connection failures still stop enqueue; they are not misreported as evidence holds.
- Older company research holds can match an existing exact name when structured
  saved research confirms the same source/name/type and canonical country/type
  checks pass. This is identity-only MATCH, never CREATE. The original held
  findings and research journal remain retained. Canonical publication uses the
  existing canonical entity values, after immutable backup, rather than uncertain
  extracted facts. A durable job checkpoint restores original staging after the
  RPC or on resume if interrupted. The deployed RPC behavior still needs verification.
- No fuzzy event merge, organization-to-company coercion, invented IMO, or deletion
  of historical canonical rows is introduced. Military formations and vessels in
  infrastructure rows are held; supplied IMOs must pass the checksum.
- The final report shows per-input published/held/failed counts, including failed
  intake sources. Shared identities can contribute to multiple source rows; source
  counts must not be summed to infer unique canonical record counts.
- Word newsletter tables are extracted. Text-based PDF newsletter extraction has
  a fallback when the existing `pc_newsletter_pdf` helper is absent; embedded article
  URLs are retained for verification. Existing newsletter image/OCR handling is
  used when available. Scanned files without usable text or that helper are held.

### Validation results and limits

`python -m compileall -q .` and
`python -m unittest test_loader_regressions test_batch_loader -q`: **54 tests pass**.
See `BATCH_TEST_REPORT.md` for the covered scenarios and exact limitations.
The mixed downstream test uses 20 real URL labels with explicitly generated test
facts plus two newsletter-style document sources: 22 independent source contexts,
24 event proposals and one shared existing company. It exercises normalization,
source grouping, canonical planning, backup/publication doubles and retry. It is
not a fresh AI extraction of those 20 articles.

The application's actual URL reader was attempted on all 20 URLs. This workspace
failed DNS resolution for every host before retrieval. No OpenAI API key is
configured here and no live Supabase service was used. Consequently no live
URL → AI → Supabase success is claimed. Four primary article pages were separately
accessible through web retrieval; that is not an application reader test.

### Install and verify in the deployed application

Replace all files in this ZIP and reboot Streamlit; confirm **Loader build v3.6.1**.
Keep existing authentication, secrets, migrations and repository dependencies.
For the existing legacy job, use **Run reconciliation again after resolving
exceptions**. Exact company identities should be matched while their broader
research holds remain in the report. Review and approve connected enrichment;
verify event links and publication audit rows in the database.

For a fresh batch, paste the URL list in `fixtures/BATCH_20_URLS.txt` and add
text-based newsletter PDFs/DOCX files to Universal intake. Review source errors,
queue the package, run population, review enrichment, then download the complete
JSON report. Confirm one result per input, no missing sources, explicit genuine
holds, and no duplicate identities/history/event links after a retry. Fresh AI
research uses the deployed API and may incur charges already authorized through
the intake consent controls. If publisher SQL must be checked, run the included
read-only function-definition query and provide its output; it changes no data.

## Full population report download in v3.5.6

The completed population screen now includes **Download complete population report
(JSON)** above the collapsed report. It exports the full displayed report, including
nested connected subject reports and event-link results. Reopened jobs assemble
saved core and connected reports before download. No rerun is required to download
a completed job's report. The individual `pc_intelligence_pipeline.py` is the only
Python file changed from v3.5.5; the ZIP also includes all earlier fixes.

This release does not override AI research holds. The copied report for the legacy
job shows four research-held company stages, two newly published items, no publication
failures, and three connected holds. The complete JSON is needed to inspect the held
findings and event link result. Company identity resolution and incident/relationship
uncertainty must be handled separately without blindly clearing research journals.
Compile checks and the existing 40 offline regression tests pass.

## Saved-review refresh fix in v3.5.5

v3.5.4 changed the mapper but retained the old persisted-review version. An
unfinished job could retain stale plans when that version already matched.
v3.5.5 compares the saved plans with freshly validated staging on each review.
Changed plans invalidate the approval checkbox. No additional web research is
performed by this refresh. Stable plans are reused without repeated writes.

The screenshot shows legacy job `e3d231b2-a03d-4596-ad67-2b48e97f72bf`, with 10
staged objects. It differs from the newer seven-object replay job. Testing its
export now produces company rows with zero events, claims and vessel histories.
The legacy source retains its own four claim records and two vessel history
records; this patch does not replace them with the newer dossier or independently
verify their factual contents. Earlier canonical writes are not deleted.

Install all patch files, restart Streamlit and verify `Loader build v3.5.5`.
Open the saved job. On the connected review screen, click **Reconcile canonical
records from saved staging** to run core matching/publication before enrichment.
Review the refreshed findings, then approve. Re-export the database to verify
publication audit rows and the event-to-vessel link. Do not re-upload the source.

Compile checks and 40 offline tests pass, including stale plans bearing the same
version and legacy-job review reconstruction against the supplied database export.
Live server-side publication still requires verification in the deployed app.

## Existing-event match and partial retry fix in v3.5.4

The attached `pc_v15_bulk_replay.py` is included. Matching now compares validated
calendar days for ISO dates and timestamps, along with exact normalized titles.
Multiple candidates, incomplete dates, and same-title date conflicts stay held.
The backup, approval and server-side publication RPC workflow is retained.
Partial reconciliation now reopens saved connected review and retries enrichment.
Shared vessel validator holds are counted in the final report. Extreme E's
company/organization conflict remains held. Historical assets are not deleted.

### Test the saved job

1. Install all files, including `pc_v15_bulk_replay.py`, restart Streamlit and
   check the `Loader build v3.5.4` marker.
2. Open job `f2a4acf4-6d66-4eb3-b544-c1ec723d4e8c`. Click **Run reconciliation
   again after resolving exceptions**. Existing staging and source evidence are
   reused; no JSON upload or repeat web research is required.
3. The planner tested against your export selects MATCH for event
   `EVT_PC_97538C73504F6A4F7B60` and MNG Maritime
   `ENTITY_A8441761CA8A779845A5`. Extreme E remains held for identity review.
4. Review and approve connected enrichment. Verify the event-to-vessel link and
   remaining holds in the report. Partial status is expected while holds remain.
5. Run the supplied full database export SQL again. Confirm the same event/vessel
   IDs, one link between them in `pc_event_links`, publication audit rows for the
   matched stages, and no duplicate history or relationships after another retry.
   Inspect canonical event fields and metadata; the server-side MATCH RPC controls
   how these are updated and still needs live verification.

### Company and document tests

- Company loader: research a known company with official evidence, review and
  approve, then retry the saved job. Verify no duplicate company profiles, offices,
  people roles or footprint rows. Ambiguous identities and invalid IMOs stay held.
- Document loader: upload a DOCX with paragraphs and table text twice. Verify the
  table text is extracted, one SHA-matched document remains and the saved company
  research job is reused. Missing issuer evidence holds identity creation; invalid
  calendar dates remain null.

Offline checks: `python -m compileall -q .` and
`python -m unittest test_loader_regressions -q` pass (39 tests). These cover
company facets, repeated uploads, source validation, event links, date matching
and partial retries with a database double. The planner also passed against the
supplied export. No live database writes were made here; deployed dependencies
and server-side publication RPC behavior still require the checks above.

## Publication-table compatibility fix in v3.5.3

`pc_v10_publication_items` has no `ingestion_job_id` column in the live schema.
Both company/vessel subject discovery and dossier event linking now scope their
publication queries with this job's `pc_staged_records.staged_record_id` values.
Queries use batches of 100 stage IDs; no schema change or new column is required.
Tests now reject attempts to use the nonexistent publication job column.

Install the files, restart Streamlit and reopen the same job. Verify the visible
`Loader build v3.5.3` marker, then approve connected enrichment again. Do not
re-extract, requeue or repeat web research. The previous attempt may have completed
company or vessel writes before the event-link lookup failed; retry reuses existing
specialist rows rather than assuming the entire attempt was rolled back.

## Resume-path fix in v3.5.2

Opening a persisted connected review now calls the current plan reconciler before
rendering or approval. Previously the session-resume route displayed the saved old
plan directly, so v3.5.1 validation could be skipped despite the new files being present.
Empty findings on a legitimate company no longer cause repeated plan rebuilding.

For the screenshot's existing job: install this patch, restart Streamlit, then reopen
that saved job. No source upload or research call is required. Verify the visible
`Loader build v3.5.2` label and the shared source-context table. Company rows must
show zero vessel name-history rows; the vessel history type must be `name`.
The repaired source context should show one claim narrative and five held findings.
Existing queue/staging counts are historical and are not reduced or deleted by review
refresh. A new replay of the included corrected JSON produces seven core proposals.

## Install

1. Extract the ZIP into the existing application repository, overwriting the matching Python files.
2. Include the new `pc_source_graph.py` beside `pc-power-admin.py`.
3. Keep the repository's existing `shared/pc_auth.py`, queue/publisher modules,
   database functions, Streamlit secrets and requirements.
4. Restart Streamlit. Restore the saved extraction or job and test the St Helena dossier again.

Updated modules: `pc_v15_bulk_replay.py`, `pc-power-admin.py`, `pc_source_graph.py`, `pc_research_dossier.py`,
`pc_graph_validator.py`, `pc_v07_core.py`, `pc_v16_research.py`,
`pc_connected_research.py`, `pc_intelligence_pipeline.py`, `pc_document_loader.py`.

## St Helena test from the supplied dossier and review CSVs

Use `St_Helena_validated_v3_5_1.json` in this ZIP for the next replay:

1. Install this release and restart Streamlit.
2. Open Load intelligence -> Validate / replay saved research dossier.
3. Upload the included validated JSON; review the five held findings.
4. Build and queue the package, then run the resolution/publication workflow.
5. Expect seven core proposals: five companies, one vessel and one event. Existing
   canonical matches may mean fewer newly created database rows.
6. In connected review, expect the vessel's former name only on its vessel row;
   companies show only their own relationships. Shared source context shows one
   event, one preserved unverified narrative, five holds and five research gaps.

This replay uses saved evidence and performs no fresh web investigation.

The five holds preserve two military formations as organisational context, two
misclassified vessel references pending proper mobile identity resolution, and the
combined `owned_and_operated_by` relationship pending role clarification.

`former_name` becomes supported `name` history with `name_role=former`. Partial month
and decade dates stay in date_evidence; exact canonical dates remain null.
Structured IMO/name identifiers are normalized for event linking. Unverified missile
attribution is removed from the event taxonomy; the original extracted description
survives as an unconfirmed narrative, not independently verified facts.

Saved unfinished review plans are revalidated on resume. This does not delete or
reclassify canonical rows that an earlier build already published. The uploaded CSVs
are review exports; they do not establish whether those canonical rows exist.

## Changes

- Freeze source-derived graph roots before web research. Research-only roots remain
  held findings attached to the source; they cannot silently become independent intake objects.
- Save the supplied source excerpt and its hash once per input source in the ingestion job's
  `source_scope.input_sources`. This is the extracted excerpt, not a full original-file archive.
- Validated dossier rows skip another generic research pass. Replay review includes
  companies, vessels, and event-only context; events and claims are retained.
- Legacy vessel-only connected review is rebuilt from persisted staging metadata on resume.
  Data not present in that metadata cannot be recovered by this patch.
- Additional v1.6 research objects remain parent-attached dependencies for review;
  they no longer spawn their own staged core objects.
- Display intake sources, queued objects, staged objects, failed queue rows and object-type
  breakdown separately. Legacy source counts are labelled unknown rather than invented.
- A matching official authority + incident reference merges event observations. An exact
  date/type/location/title/identified-asset context can also match. Conflicting fields remain
  marked contested, with both source observations preserved. The retained display value is
  not adjudicated truth; an analyst must resolve the disagreement.
- Reuse an existing event ID when the same identity is found in `pc_events` before enqueue.
  Uncertain same-context matches block enqueue for analyst resolution. Different official
  references from the same authority establish distinct incidents.
- Source-derived verified IMO involvement can populate `pc_event_links` after canonical
  event publication and analyst approval. No asset link is inferred merely from sharing a source.
- Company publication retains pending ownership as a hold, rejects uncited company identity,
  selects the newly saved review, and permits retry of partially published company jobs.
- Document uploads use their byte hash to reuse the same document and connected research job
  on sequential retries. DOCX tables are extracted. Invalid calendar dates become null.
  An ambiguous or unverified new issuer remains held. Government/think-tank issuers are not
  automatically sent through commercial-company fleet research. Failed documents are reported.
- Saved publication reports and holds survive a Streamlit restart.

## Local verification

From this directory:

    python -m compileall -q .
    python -m unittest test_loader_regressions -v

32 offline regression tests pass. They use an in-memory database/query contract and mock
research responses; they make no network calls or production writes. Coverage includes
source-bounded investigation, repeat document upload, DOCX tables, company publication
retries, pending ownership, IMO verification, same/different events, source disagreements,
existing-event binding, full connected replay, and event-to-vessel links.

`test_graph_validator.py` now uses the supplied St Helena JSON in `fixtures/`.
Run `python test_graph_validator.py` for the dedicated fixture test.
Historical `README_v3_4_*.txt` notes refer to earlier releases.

## Live test checklist

1. Replay the St Helena JSON: verify company and vessel subjects, the event, claims,
   identity history and explicit held findings are all visible. Seven staged objects may be
   legitimate; inspect the object-type breakdown rather than interpreting it as seven sources.
2. Feed two URLs reporting one incident with the same official reference: expect one event
   proposal with two source observations. Different incidents must remain separate.
3. Research a company: review offices, people, relationships, vessels and gaps; publish,
   retry and verify that the same objects are reused.
4. Upload the same document twice: expect one document record, one company research job
   where applicable, and stable entity links. Review issuer holds and source evidence.

## Limits requiring live validation

The provided ZIP did not include `pc_v15_bulk_replay.py`, `pc_v08_content.py`, shared auth,
other existing worker modules, or the current Supabase schema/RPC definitions. They remain
required from the application repository. End-to-end queue/publication behavior, permissions,
constraint compatibility and concurrent ingestion cannot be verified offline here.

The source registry and observations use existing JSON metadata/source_scope; no new SQL
is included. They do not create a new global normalized `pc_event_observations` table.
Document hashing prevents sequential duplicate uploads; concurrent uploads need a database
unique constraint/transaction for a hard guarantee. Existing historical duplicate documents
without hashes are not automatically merged. Similarly, simultaneous jobs still rely on the
existing canonical publisher's database constraints.

Generic saved-dossier transactions/contracts/projects whose specialized mapping is unverified
remain visible holds, not silently converted records. The dedicated company research schema
continues to publish its supported transaction/contract/project findings.
