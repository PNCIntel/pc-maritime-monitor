# P&C Trade System v3.0 — Excel / GitHub / Streamlit Deployment

This is the complete Excel-backed GitHub deployment package. It preserves the current v2.9 data model and adds the v3.0 P&C Core Intelligence product lens without forking the data.

## Streamlit entry points
- `app.py` — P&C Trade System v3.0, including the temporary **P&C Intelligence Test** workspace.
- `pc_intelligence_app.py` — separate P&C Intelligence proof-of-concept using the same `/data` Excel files.

## New v3.0 Trade System UI
- P&C Intelligence Test → Operating Picture
- P&C Intelligence Test → MARSEC
- P&C Intelligence Test → Compliance & Exposure
- Network → Aviation
- Companies → Share Price
- Companies → Security & Risk
- Vessels → Security & Compliance
- Ports → Security & Disruption

## Data model additions already present
- `02_maritime.xlsx` → Vessel Restrictions plus PGSA-linked canonical vessels/relationships.
- `09_intelligence.xlsx` → security monitoring and Security Product View.
- `10_sources_evidence.xlsx` → Japan Coast Guard, Korea Coast Guard, Indian Coast Guard, DG Shipping and PGSA source feeds.
- `13_events_hazards.xlsx` → MARSEC sample events and impact chains.
- `14_trade_policy_compliance.xlsx` → Compliance Regimes, Compliance Designations and Compliance Exposure.
- `07_corporate_markets.xlsx` → Company listings, financial metrics, investments and share-price history remain part of the same data set.

## GitHub / Streamlit deployment
Replace the files in the existing GitHub repository with the contents of this package, preserving the `/data` directory. Streamlit should continue to point at `app.py`. No Supabase connection is required for this Excel-backed build.

The future Supabase/PostgreSQL migration should normalize these exact relationships, not create separate trade/security databases.


## Product separation — v3.0.3
P&C Intelligence and the P&C Trade System remain separate user experiences. They read the same canonical data model, but P&C Intelligence does not send users into the Trade System. Relevant port, company, vessel, system and compliance context is displayed locally within the Intelligence app.
