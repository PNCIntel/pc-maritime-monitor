# P&C Independent Risk Prototype v7

Run the SQL file in Supabase SQL Editor on a test/staging database first. It adds two views and one date-parameterized function. It does not modify any event, third-party GSA or existing assessment records.

## Inputs and scope
- `pc_intel_event_details`, `pc_events`, `pc_v07_event_assessments`, `pc_event_locations`, `pc_event_impacts`.
- Latest event assessment is selected by version and assessment ID.
- P&C event significance is a **severity-derived index**, not an independently approved risk probability. Any unclear severity returns NULL; official evidence is not inferred merely from link count.
- Regional outputs are **MODEL_DRAFT_NOT_APPROVED**. Require an explicitly recorded `region_code` in event or details rows. No string matching or guessed geography. If region codes are absent, there will be few/no region results; next step is to attach the existing curated geography graph using checked linkage.
- Requires at least 3 recent incidents, 3 severity-scored and 2 confirmed, else `NOT_RATED`. Frequency trend requires 3 events in each comparison period and materially different counts; it describes observed incident frequency only.
- `LOWER_OBSERVED_SEVERITY` is NOT "safe" or low regional threat. Sparse/biased reporting, severity taxonomies, attribution issues and absence of exposure denominator limit inference.
- The Trade view passes through source-derived `commercial_impact`, `operational_impact`, `what_it_means` and `monitoring_indicators` with status labels; potential commercial effects are not confirmed losses.
- Do not promote these preliminary scores into `pc_risk_assessments` or show them as approved public P&C ratings without calibration and human review.

## Suggested QA
1. Run read-only summary and 25-region check printed after COMMIT.
2. Check actual severity values: `SELECT severity_label, count(*) FROM public.pc_v7_event_analytical_basis GROUP BY 1 ORDER BY 2 DESC;`
3. Check region code coverage (must distinguish event region and company jurisdiction).
4. Compare several dates via `SELECT * FROM public.pc_v7_independent_region_risk_at('2026-09-30');`.
5. Manual review: UAE/Hormuz conflict, European rail strikes, ReCAAP, Black Sea. Adjust weights only with documented methodology and expert calibration; comparisons to third parties must remain attributed and separate.

## App connection
- Security: select event basis with date/risk/verification filters; display `pc_event_scoring_status`, region function historical results, and event narrative/monitoring indicators.
- Trade: query `pc_v7_trade_event_intelligence` for business narrative, prospective impacts, analytical indicators and source URLs. Link to company/facility/corridor graph via verified existing relationship views, never entity-name fuzzy matching.
- This release is SQL only; the current Streamlit UI has not been modified or live-tested.
