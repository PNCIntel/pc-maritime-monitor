# Trade System v3.3 Build — 11 September 2026

**Release:** `v3.3.0-reference-intelligence`

## Added
- Signal Group market-monitor reference layer, including Week 36 dry-bulk observations.
- IMO authoritative security layer with 75 Middle East confirmed incidents in the current snapshot.
- IMO Red Sea, Hormuz evacuation, international-straits and Black Sea/Sea of Azov baselines.
- Global 1,377-port reference population and 2050 port-fuel scenarios.
- FTA/LSBCI and World Bank/UNCTAD connectivity/reference registry.
- Historical port accident benchmark layer.
- Port operational-delay causal-model staging.
- Chokepoint/market-transmission reference series.
- Accuracy Shipping historical stock-price schema/sample.
- Ocean Melody / Qingdao Beihai / CSSC connected canonical event graph.

## Legacy test behavior
The Streamlit app still starts from Excel. Supabase remains optional. Large research datasets are retained in `external_data` for lazy use and later Postgres ingestion.
