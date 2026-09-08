# P&C Trade System App v1.21 — Human-readable display layer

- Internal canonical keys remain in the data model for joins but are suppressed from user-facing tables.
- Company, vessel, port, terminal, rail, corridor, ferry, aircraft and asset foreign keys are resolved to canonical names.
- Multi-value entity keys separated by semicolons are resolved individually.
- Relationship enums such as `PART_OF`, `MAJORITY_OWNED_BY`, `OWNER_OPERATOR`, `JV_PARTNER` and `OWNS` render as plain English.
- Transaction fields such as Investor / Buyer IDs and Co-Investor / Partner IDs render as organization names under human-readable headers.
- Record-management IDs such as Program ID, Deal ID, Relationship ID and other internal row keys are hidden from display tables.
- Source keys are hidden when a URL/publisher/source field is already visible; otherwise they resolve to publisher names where possible.
- Sidebar build marker updated to APP BUILD v1.21.
