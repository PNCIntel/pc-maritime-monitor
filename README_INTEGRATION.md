# P&C seven-application UI integration — first pass

This bundle includes the two edited shared renderers from the files supplied on 8 October 2026, the four current launchers, the three earlier starter launchers, and pc_portfolio.py.

## Deploy
Replace `pc_terminal.py` and `pc_market_lenses.py` in the application repository with the versions in this archive. Preserve the existing `shared/`, `pc_drilldown.py`, `pc_corporate_network.py`, and any other existing imports. Do not rename or replace database tables. Existing four launchers remain unchanged and continue to call the same renderer functions.

Add the three new launcher files and `pc_portfolio.py` only when ready to deploy their starter dashboards.

## Changed
- Technical database terminology removed from primary UI headings, search match explanations, the left navigation sidebar and facility details.
- Trade and Strategic Industries market selector labels are business-oriented.
- Search continues to use the existing indexed RPC with fallback and keeps original IDs internally.
- Current specialist company, fixed-asset and mobile-asset separation preserved.

## Not yet changed / requires testing
- Fujairah's empty connected-facilities count is NOT proven fixed. The existing `pc_terminal_asset_dossier` RPC and `pc_terminal` local fallback must be checked against live Supabase records.
- No schema change or live database tests; this is a presentation pass.
- Three new markets are read-only search starters, not full analytical products.
- The source repository includes additional imports not supplied; deploy into the existing repository, not this zip alone.
