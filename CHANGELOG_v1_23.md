# v1.23 — Embedded Header / Metadata Fix

- Detects CSVs that contain a title, scope note and summary statistics above the actual table header.
- Promotes the real field row before rendering, preventing `Unnamed:` columns and metadata rows from appearing as records.
- Fix applies generically to research-universe datasets such as infrastructure investors, tanker fleet universe, fleet rankings, fleet research universe, weather/labour events and carrier deployment seeds.
- Preserves the v1.22 map layer and v1.21 human-readable ID translation.
- Sidebar build identifier updated to v1.23.
