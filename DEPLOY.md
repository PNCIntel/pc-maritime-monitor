# P&C Loader Reconciliation v8 (repair stage 1)

Run `01_hormuz_repair.sql` in Supabase SQL editor. It creates an independent **review ledger** with 11 Hormuz assessment observations, explicitly marking five second-job records as repeated imports. Six unique source keys are distinct review cases, **not yet six independently confirmed attacks**. Three 29 September keys remain anonymous until source-to-vessel attribution is verified. This script **does not update or delete source assessments, canonical events, risk ratings or linked data**.

Run `02_global_repeat_review.sql` to expose database-wide repeated content candidates. The view is diagnostic and does not merge identical text from potentially distinct incidents.

## Manual approval gate
1. Verify the six source observations against individual incident documents, notices, vessel identities and dates. Use the link sources listed in the ledger.
2. Check for existing canonical `pc_events` entries and linked vessel/facility records. Never create a duplicate canonical event.
3. Only then assign `linked_event_id`, source-specific vessel identity and mark `review_status='reviewed'` in the ledger, with `reviewed_by` and `reviewed_at`. Do not edit underlying assessments unless the provenance is preserved and the source relation has been verified.
4. Do not count unapproved review cases or repeated imports as additional incident-frequency evidence. The existing v7 scoring function is **not yet repaired** for geographic resolution or repeated source-event identity. Do not publish its output as approved regional threat ratings.

### Expected output
Case roles: five `repeat_import`, three `ambiguous_distinct_case`, three `primary_observation` (one 14 Sep, two other source cases). If any are missing, review the source ingestion and don't approve mappings.

## Global loader hardening next
- A durable, unique source-observation identity should use provider/document identifier, source publication reference, external source record ID where durable, and a revision fingerprint; `input:n` alone is only batch-local.
- Separate multiple incidents within a single article by stable victim asset/date/location identifiers and preserve attribution status.
- Keep source observation, canonical event, and versioned assessment as separate linked objects.
- Enforce a publication gate: no assessed event can be counted in independent regional incident frequency without confirmed canonical identity, credible date and geographical evidence. Trade and Security read the same approved canonical event but show distinct facets.
