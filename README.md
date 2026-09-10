# P&C Trade System v1.17 — Rail Networks & Intermodal Connectivity

This is the complete GitHub + Streamlit deployment package.

## v1.17 additions
Rail is now a first-class movement layer alongside ports, vessels, ferries, aviation and inland logistics.

New runtime tables:
- `rail_operators.csv`
- `rail_networks.csv`
- `rail_nodes.csv`
- `rail_links.csv`
- `rail_relationships.csv`
- `rail_fleet.csv`
- `rail_connections.csv`
- `rail_news.csv`

## Initial rail population
- 19 rail operators / infrastructure authorities
- 20 named networks and corridors
- 62 physical rail nodes
- 38 origin → destination movement links
- 26 network/company relationship records
- 5 rolling-stock aggregate records
- 32 direct rail-to-port / rail-to-asset connections
- 5 rail news/development records

Initial coverage includes:
UAE National Rail Network, Hafeet Rail, Saudi East Freight, Middle Corridor / BTK,
CN, CPKC, Alameda Corridor, BNSF, Union Pacific, Norfolk Southern,
Transnet ContainerCor / NorthCor, Tanger Med / ONCF, HHLA / METRANS,
Hamburg Port Railway, Western Dedicated Freight Corridor and CONCOR.

## Streamlit
`app.py` is v1.17 and includes a new **Rail Networks** page.
Company pages show linked rail networks, rail nodes and rolling-stock aggregates.
Port pages show canonical rail connections.
Ask P&C searches rail networks, nodes, links and rail news.

## Model workbook
`model/PC_Trade_System_Intelligence_Model_v1_17_Rail_Networks.xlsx`

Blank values mean not yet verified — never zero.


## App v1.19 visualization upgrade
The Streamlit application now includes an Entity Explorer, relationship graphs on company/port/vessel/rail views, and dynamic Watch Areas assembled from the canonical corridor and relationship model. The underlying data baseline remains Model v1.17.


## v1.22 map layer
The Streamlit interface includes map views for canonical ports, geolocated event observations, rail-linked ports, ferry terminals and corridor/watch-area gateway ports. Maps use only coordinates already present in the model.
