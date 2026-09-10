# v3.0.6 — Streamlit Duplicate Widget Key Fix

Fixed `StreamlitDuplicateElementKey` in Trade System connected-event cards.

- Each `render_event_cards()` invocation now receives a unique render scope.
- Association button keys include render scope, event, entity type, entity ID and relationship.
- `Open source` link buttons now also receive explicit unique keys.
- No data model changes. This is a Streamlit presentation/runtime fix.
- Both `app.py` and `pc_intelligence_app.py` pass Python syntax validation.
