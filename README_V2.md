# Power & Corridors: Seven-application UI, v2

This package contains all seven Streamlit entry points, the two updated existing dashboard engines, and one new read-only specialist engine `pc_specialist_markets.py` for the three new products.

## New, functional applications

- `PC_Capital_Ownership_app.py`: corporate relationships, portfolio investments, agreements and company-specific drilldowns from `pc_entities`, `pc_company_relationships`, `pc_company_portfolio_positions`, `pc_contracts` and `pc_contract_participants`.
- `PC_Commodities_Resources_app.py`: energy/fuels, food/agriculture, minerals/metals and industrial materials views across `pc_assets`, `pc_entities`, `pc_events` and `pc_project_details`. Categorisation is keyword-based discovery, NOT validated commodity flows or inventories.
- `PC_Markets_Freight_app.py`: reported metrics from `pc_port_metrics`, services from `pc_transport_services`, infrastructure capacity from `pc_assets`, and recent developments from `pc_events`. It does NOT fabricate freight-rate series or combine incompatible units.

## Deployment

1. BACK UP existing Python files, then copy the package's `pc_terminal.py`, `pc_market_lenses.py`, `pc_specialist_markets.py` and seven launcher files to the same folder as the existing P&C application modules. You may retain original launcher filenames in Streamlit deployment settings.
2. Preserve all other existing dependencies (`pc_drilldown.py`, `pc_corporate_network.py`, `shared/pc_db.py`, etc.). The ZIP is **not a standalone deployment repository**.
3. Existing four launchers keep the existing renderer functions. The new three launchers import `pc_specialist_markets.render`.
4. Use existing database credentials and RLS permissions. The specialist engine uses the existing `pc_db.client(service=False)` where available; it makes only SELECT calls.
5. Start individually: `streamlit run PC_Capital_Ownership_app.py`, or the corresponding Commodities or Markets file. Set your Streamlit hosting entrypoints accordingly.
6. Check access to `pc_company_relationships`, `pc_company_portfolio_positions`, `pc_contract_participants`, `pc_port_metrics`, and `pc_transport_services`; missing table permissions produce partial or empty views and must be diagnosed, not assumed to mean no records.

## Limits

- Tested only by Python compilation. No live database connection or GUI/browser acceptance tests performed.
- Existing four dashboards were relabelled in the prior v1 package; more profound profile and map improvements are outstanding.
- Capital totals are counts of fetched relationship/contract rows, not sums of valuation or investments; the UI explicitly labels this.
- Commodity categorisation is text-based and may produce false negatives/positives. The next iteration should implement validated commodity, flow and transport-lane joins once we know which structured tables contain these facts.
- Freight indicators remain typed source values; rates require a verified structured observation schema.
- Company selector currently loads the first 3,000 returned entities; search may be incomplete in larger corpora.
