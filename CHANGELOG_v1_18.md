# P&C Trade System — App v1.18

Model baseline: Intelligence Model v1.17 Rail Networks & Intermodal Connectivity.

## Added
- Company Relationship Graph as the first company-profile tab.
- Entity Explorer for canonical companies, ports, terminals, vessels, rail networks/nodes, corridors and other registered entities.
- Dynamic graph depth, relationship-layer filters and node caps for readable network exploration.
- Relationship evidence table beneath graphs.
- Port system relationship graph.
- Vessel ownership / operating network graph.
- Rail network relationship graph.
- Watch Areas page driven by the canonical corridor registry.
- Panama Canal watch-area assembly from the existing corridor, Panama port and terminal/operator records.
- Gateway-port, terminal, connection and intelligence-evidence views inside Watch Areas.
- Operational, gateway, security and network indicator framework for each watch area.

## Data-layer changes
- app.py now loads relationships.csv, entity_registry.csv, corridors.csv, system_nodes.csv and system_links.csv.
- Existing relationship-bearing tables are normalized at runtime into a single graph-edge layer; source CSVs remain unchanged.
- No existing canonical model data was removed or overwritten.

## Deployment
- Added graphviz Python dependency for Streamlit graph rendering.
