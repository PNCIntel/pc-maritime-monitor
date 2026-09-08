# P&C Trade System v1.19

## Fixes
- Fixed `StreamlitInvalidHeightError` in `safe_display()` by omitting dataframe height unless a valid explicit integer height is supplied.
- Improved dark-theme readability after Streamlit UI changes: sidebar headings, navigation labels, captions, widget labels, tabs, expanders, and controls now use explicit high-contrast P&C colors.
- Strengthened sidebar/background styling so Streamlit defaults cannot render dark text on the dark navy surface.
- Improved link and muted-text contrast.
- Reworked Operating Picture KPI cards from seven narrow columns into a 4 + 3 layout to prevent severe text wrapping on desktop/laptop widths.
- Preserved v1.18 Entity Explorer, relationship graphs, Watch Areas, rail, fleet, infrastructure and intelligence features.
