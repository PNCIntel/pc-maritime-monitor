# Native OFAC SDN import

Apply 061_ofac_native_import.sql after migrations 055 and 060, then restart Power Admin and the shared terminals.

In Power Admin choose Load documents. Upload the UAE PDF alone and select Analyse & save documents. Verify 472 source rows and inspect held identifiers. Upload sdn_enhanced.xml separately, then select Import complete OFAC XML. XML ingestion does not use OpenAI.

The supplied XML contains 19,488 designations, including 1,539 vessels; 50,128 name variants; 22,885 identifiers; 25,482 address variants; 56,176 features; and 9,126 relationships. Its source timestamp is 2026-10-02. These are source-file parser counts, not confirmed live database counts.

Matching uses checksum-valid IMO against the complete existing mobile asset registry, including vessels previously loaded from PGSA. Existing records and their provenance remain intact. OFAC designations link directly to the same hull. A UAE restriction is retained separately from an OFAC designation. Names may differ across sources. No company ownership is inferred from a shared name. All native relationships and unresolved targets remain stored as source evidence.

Use the UAE / OFAC vessel overlap button in Trade, Sanctions or Intelligence after both imports. Open a vessel to inspect its direct sanctions designations and source document evidence alongside its existing relationships. This view does not claim a separate PGSA membership count; the existing registry is used for canonical matching.

The original XML is retained as verified private chunks with a reconstruction manifest. Imports use transactional, deterministic batches and support retrying the same file. Completion requires stored source-field counts to match parser counts. 69 vessel entries lack a single checksum-valid IMO and require identity review; three relationship targets are outside the supplied export. Those records are preserved rather than guessed.

Validation: 15 offline tests pass, including parser rejection cases, existing-IMO reuse and original reconstruction integrity. Python modules compile. SQL and the importer have not been executed against the live Supabase database from this workspace. An incomplete run must not be treated as a completed sanctions load.
