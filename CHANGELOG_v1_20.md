# P&C Trade System App v1.20

- Removed dataframe `height` forwarding from `safe_display()` entirely to eliminate `StreamlitInvalidHeightError`.
- Explicitly treats the second `safe_display` argument as a row limit only.
- Strengthened sidebar/radio/caption contrast selectors for current Streamlit/BaseWeb markup.
- Added a visible `APP BUILD v1.20` marker in the sidebar so deployments can be verified immediately.
- Retains v1.18/v1.19 Entity Explorer, relationship graphs, Watch Areas, rail, infrastructure and 4+3 Operating Picture metric layout.
