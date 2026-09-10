# P&C Intelligence App Architecture — v3.0 Excel-backed

## Product purpose
The P&C Intelligence Streamlit app is a security-first product lens over the same canonical Excel data used by the P&C Trade System. It does not fork vessels, companies, ports, aircraft, events, sanctions, or source records.

## Navigation

### Intelligence Desk
- Operating Picture
- Alerts & Incidents

### Forward Monitoring
- Watch Areas
- Monitoring & Indicators

### Domain Intelligence
- Maritime Security
- Ports & Infrastructure
- Aviation & Movement
- Sanctions & Compliance

### Discovery
- Intelligence Search
- Source Monitor

## Data pulls
- `01_core_entities.xlsx` — Companies / canonical entities
- `02_maritime.xlsx` — Ports, Vessels, Vessel Restrictions
- `05_aviation.xlsx` — Aircraft Registry
- `06_infrastructure.xlsx` — Assets, Dry Ports, Economic Zones
- `09_intelligence.xlsx` — News Registry, Strategic Events, Event Observations, Monitoring, Disruption Watch, Weather Labour Events
- `10_sources_evidence.xlsx` — Sources, Source Feeds
- `13_events_hazards.xlsx` — Events, locations, asset/company links and impact chains
- `14_trade_policy_compliance.xlsx` — Government sanctions, PGSA/compliance regimes, designations, exposure and taxonomy

## Product logic
The app follows the same intelligence logic as the P&C Intelligence website:
1. Immediate — incidents and alerts
2. Situational — current operating picture
3. Analytical — connected entity / asset / commercial implications
4. Forward — monitoring, indicators and triggers

## Visual system
- Near-black background
- Warm ivory primary text
- Restrained P&C gold for hierarchy, active states and key metrics
- Fine grey borders
- Editorial cards rather than brightly coloured dashboard widgets
- Minimal rounded styling

## Deployment
Deploy `pc_intelligence_app.py` as a second Streamlit Community Cloud app from the same GitHub repository and branch as the Trade System.

The existing `app.py` remains the P&C Trade System.


## Product separation — v3.0.3
P&C Intelligence and the P&C Trade System remain separate user experiences. They read the same canonical data model, but P&C Intelligence does not send users into the Trade System. Relevant port, company, vessel, system and compliance context is displayed locally within the Intelligence app.
