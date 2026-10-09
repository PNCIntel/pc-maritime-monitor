# P&C Dual Security and Trade Event Lenses — v6

1. Back up working repository modules. Use a test branch.
2. Apply `sql/20261009_dual_event_lenses.sql` in Supabase after existing `pc_intel_event_details` and related views.
3. Add `pc_event_dual_lens.py` alongside existing modules and replace `pc_intelligence_presentation.py` with included version. Leave other modules intact.
4. Restart Trade and Intelligence and clear their cached results. Open a known event dossier in each product.
5. Verify a dated `pc_risk_assessments` record linked by `pc_risk_assessment_events` produces a displayed risk level ONLY if `approval_status` is approved/published; otherwise it shows Not assessed.
6. Verify a strike or port attack with `pc_logistics_event_impacts` shows operational effects in Trade without changing its event identity.
7. Verify missing impact data displays 'not recorded', not 'no commercial impact'.

**Scope:** This integrates a dual-lens panel in existing event dossiers and creates reusable SQL views. It does not yet migrate all home and sidebar sections. SQL was composed against supplied table and column names; live database compilation is unverified. If a schema error arises, return the exact error rather than applying guessed fixes. Existing models are not modified.
