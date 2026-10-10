# Generic Company Network patch

Replace your deployed `pc_terminal.py` with the supplied file and add `pc_company_network_ui.py` alongside it. Keep your existing `pc_market_lenses.py` and launcher unchanged. The supplied market lens copy is for reference only.

Every company dossier now has Overview, Corporate Tree, and Network & Evidence. The third view reads the existing universal `_entity_graph_neighborhood` for the selected canonical entity. No hardcoded Noatum or AD Ports IDs, no Noatum-only views, no SQL changes. Counts are direct-link counts for the selected company (not the V6 45-group-wide distinct assets). Entity/asset Open actions use existing context navigation.

Syntax-checked locally. Actual Supabase/Streamlit deployment has not been run here.
