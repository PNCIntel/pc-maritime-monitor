# P&C analyst loader — targeted Phase 1 patch

## Replace files (after backing up current deployed versions)
- `pc-power-admin.py` -> existing Power Admin entrypoint, whatever the repo's configured filename is.
- `pc_intelligence_pipeline.py` -> repo module with that name.

Deploy both together. No SQL migration in this patch. Existing deployed supporting Python modules remain mandatory.

## What is changed
- Enables complete-source AI research mode as the default; makes background research mandatory when using the standard publishing path.
- Enqueues research for every UNPUBLISHED core staged record, including exact canonical name matches and events, rather than only unresolved identities.
- Repeats planning after a research pass to capture newly staged dependent core objects.
- Prevents publishing while research tasks remain pending, running or unapplied 'researched'.
- Stops displaying a misleading success banner when holds, failures or agreement-sync warnings remain.
- Removes job IDs from the analyst queue confirmation/metric (identifiers remain in internal reports).

## Explicit remaining limits / NOT verified
- Does not follow every individual newsletter headline to a separately retrieved article. Source-link discovery and reader matching must be tested using the supplied PDF newsletters and the missing `pc_newsletter_pdf.py` module.
- Does not add full specialist-table writers (subsidiaries, ownership history, vessel name history, rail/protests, regulatory milestones); those require tested persistence adapters to existing DB procedures.
- Does not guarantee app visibility; both dashboard readers need canonical relevance/filtering correction and post-write retrieval tests.
- Does not retroactively re-research already-published records. Historical data-quality repair must use a separate staged enrichment workflow.
- An existing job fingerprint can cause job reuse; start a new extraction for a new research batch, and retain historical jobs for audit.
- This patch is STATIC/MOCK TESTED only. Do not run against production without staging trial and rollback copy.

## Analyst experience target
1. Add URL(s), newsletter PDFs, reports, structured load files; consent to public reader + OpenAI where relevant. Click Prepare sources.
2. Click Queue package, then Research, resolve & POPULATE DATABASE (the long-running worker resumes persisted work).
3. Review only genuine evidence/identity exceptions. Admin monitors the full report and reader parity separately.

## Acceptance trials
- New Svitzer homepage import must update the one canonical company; no office/team/contract/product fake companies.
- Original article links from email newsletters must get independent source retrieval (NOT IMPLEMENTED BY THIS PATCH).
- St Helena / MNG Maritime histories, ownership and operator differences require specialist history writer and source tests (NOT IMPLEMENTED BY THIS PATCH).
- No batch called 'fully completed' until specialist-table and reader-parity tests pass.
