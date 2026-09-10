# GitHub Update — v3.0 Excel Build

For the current test deployment, upload/replace **the whole repository** with this package.

Keep Streamlit main file: `app.py`

Required runtime files:
- `app.py`
- `requirements.txt`
- `.streamlit/config.toml`
- entire `data/` folder

Optional second Streamlit app:
- `pc_intelligence_app.py`

Future-only files:
- `supabase_seed_v3/`

Do not split the Excel data folder between the two applications. Both applications should read the same canonical files.


## P&C Intelligence app update
`pc_intelligence_app.py` has been rebuilt as the full security-first product lens. Its navigation now covers Operating Picture, Alerts & Incidents, Watch Areas, Monitoring & Indicators, Maritime Security, Ports & Infrastructure, Aviation & Movement, Sanctions & Compliance, Intelligence Search and Source Monitor. It reads the same Excel workbooks in `/data` as `app.py`.


## v3.0.1 Trade integration update
- Removed the standalone `P&C Intelligence Test` workspace from `app.py`.
- Added a compact risk/disruption snapshot to the Trade System Overview.
- Added `Maritime Disruptions` under Operations for trade-facing MARSEC/casualty/SAR/pollution exposure.
- Renamed `Sanctions` to `Sanctions & Compliance` and integrated PGSA / operational compliance and secondary counterparty exposure there while preserving the distinction from government sanctions.
- Retained company `Security & Risk`, vessel `Security & Compliance`, and port `Security & Disruption` drill-downs as embedded trade-risk context.
- `pc_intelligence_app.py` remains the separate dedicated P&C Intelligence product using the same Excel data.

## v3.0.2 linked-event navigation
- Trade `Maritime Disruptions` event cards now expose associated ports/assets, companies and systems beneath each incident.
- Linked canonical ports/companies/vessels can be opened directly inside the Trade System.
- Legacy Rotterdam event asset aliases were normalized to canonical `PORTG0242` so incidents appear on the Port of Rotterdam profile.
- The Rotterdam explosion now includes the Port of Rotterdam Authority as an associated company/authority context.
- Trade System accepts `?port=`, `?company=` and `?vessel=` deep-link parameters from the Intelligence app.


## Product separation — v3.0.3
P&C Intelligence and the P&C Trade System remain separate user experiences. They read the same canonical data model, but P&C Intelligence does not send users into the Trade System. Relevant port, company, vessel, system and compliance context is displayed locally within the Intelligence app.
