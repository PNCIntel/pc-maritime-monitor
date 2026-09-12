# P&C metadata-driven staging migration

This migration evolves the existing `pc_staged_records` JSON review queue into a metadata-driven ingestion layer without breaking the current Power Admin workflow.

## What it adds

- `pc_meta_entity_types` — logical entity → physical canonical table registry.
- `pc_meta_columns` — model/column metadata, keys, identifiers, references and staging rules.
- `pc_meta_relationship_types` — relationship metadata.
- `pc_meta_match_rules` — ordered entity-resolution rules.
- `pc_entity_identifiers` — IMO/MMSI/LEI/UNLOCODE/etc. → canonical P&C ID mapping.
- `pc_staged_values` — generic table/column/value staging under each existing `pc_staged_records` envelope.
- `pc_staged_relationships` — relationships can be resolved independently of entity creation.
- `pc_resolution_log` — auditable resolution decisions.
- Additional resolution fields on `pc_staged_records`.
- Model registry and staging-resolution views for Power Admin.

## Key procedures/functions

- `pc_refresh_model_registry()` — sync registered canonical tables/columns from `information_schema`.
- `pc_expand_staged_payload(staged_record_id)` — expand existing JSON payloads into row-level staging values.
- `pc_register_identifier(...)` — add external/natural identifiers to the identifier registry.
- `pc_resolve_staged_record(staged_record_id)` — resolve one staged object using metadata rules.
- `pc_process_ingestion_job(ingestion_job_id)` — resolve a complete staged batch.

## Current initial resolution policy

For vessels/mobile assets:

1. IMO exact match.
2. MMSI exact match.
3. Normalized vessel-name match.
4. If no deterministic match exists, status remains `NEW` for review.

Fuzzy matching is deliberately not auto-promoted. Ambiguous records remain in staging.

## Compatibility

The existing `pc_staged_records.payload` field and Power Admin review/apply workflow remain intact. The new `pc_staged_values` table is an additive layer, which means the UI can be migrated gradually rather than requiring an immediate rewrite.

## Recommended next step

Update Power Admin Batch Staging so uploads first create a `pc_staged_records` envelope, expand the incoming row into `pc_staged_values`, then call `pc_process_ingestion_job()`. The Review Queue should display `resolution_status`, `resolved_entity_id`, `resolution_method`, and `candidate_count` before canonical apply.
