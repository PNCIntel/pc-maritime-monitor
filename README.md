# P&C Analyst Loader v3.5.0 — connected source resolution

This is a replacement-file patch for the existing P&C application repository.
It is not a standalone application or a database migration.

## Install

1. Extract the ZIP into the existing application repository, overwriting the matching Python files.
2. Include the new `pc_source_graph.py` beside `pc-power-admin.py`.
3. Keep the repository's existing `shared/pc_auth.py`, queue/publisher modules,
   database functions, Streamlit secrets and requirements.
4. Restart Streamlit. Restore the saved extraction or job and test the St Helena dossier again.

Updated modules: `pc-power-admin.py`, `pc_source_graph.py`, `pc_research_dossier.py`,
`pc_graph_validator.py`, `pc_v07_core.py`, `pc_v16_research.py`,
`pc_connected_research.py`, `pc_intelligence_pipeline.py`, `pc_document_loader.py`.

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

24 offline regression tests pass. They use an in-memory database/query contract and mock
research responses; they make no network calls or production writes. Coverage includes
source-bounded investigation, repeat document upload, DOCX tables, company publication
retries, pending ownership, IMO verification, same/different events, source disagreements,
existing-event binding, full connected replay, and event-to-vessel links.

`test_graph_validator.py` is an inherited test that requires the original St Helena JSON
fixture at its configured external path; that fixture was not supplied with this ZIP.
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
