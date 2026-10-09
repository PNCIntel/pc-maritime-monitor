# P&C Trade + Security release v4 (2026-10-09)

Purpose: restore a map-led customer experience with live PostgreSQL delivery views, preserving the previous object dossiers and application entry points.

## Deployment order
1. Back up the currently deployed `pc_visual_workspaces.py` and other Python files.
2. In Supabase SQL Editor run `sql/20261009_trade_security_v4.sql` **after** the previously installed `pc_delivery` and `pc_intel` views.
3. Validate the new views with:
   - `SELECT name,country FROM public.pc_v4_trade_facilities WHERE name ILIKE '%Fujairah%' OR name ILIKE '%Khalifa%';`
   - `SELECT map_precision,count(*) FROM public.pc_v4_security_geo GROUP BY map_precision;`
   - `SELECT event_id,title,map_precision FROM public.pc_v4_security_geo WHERE title ILIKE '%Hormuz%' LIMIT 20;`
4. Replace only `pc_visual_workspaces.py` in a **test branch** with the file in this package. Keep all your other deployed files, Streamlit secrets, and configurations unchanged.
5. Test Trade home and Intelligence home, plus existing deep links to Rotterdam, Fujairah, AD Ports and several event dossiers.

## Important implementation limitations
- This is an iterative release, not a fully rewritten platform; dossiers and operational sidebar sections still use parts of the existing Python renderer.
- Live SQL views make fresh SQL-loaded data available on subsequent queries; the client caches results for 75 seconds.
- Infrastructure queries are server-side for search/country but map layer filtering is presently per page (clearly disclosed in UI). The first 250 matching rows are shown on each page; this is not a global completeness claim.
- Security map markers either represent verified event coordinates (`event_location`) or linked-facility context (`linked_facility_context`), never an invented exact attack location.
- Only records with existing documented risk fields show ratings. Neither HIGH nor INCREASING is inferred from event counts.
- The event view chooses one linked location per event for initial plotting; richer multiple-location spatial modelling is a subsequent enhancement.
- When Supabase view permissions/RLS or dependent views are unavailable, the application shows an error rather than a fabricated zero.
- The corporate-tree renderer in `pc_terminal.py` is retained as-is; this release does not claim to solve all company-dossier performance issues.
