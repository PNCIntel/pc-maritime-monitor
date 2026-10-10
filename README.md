# Generic company Network & Evidence – routing correction

## Cause
The previous patch updated `_render_company_terminal` but Noatum and AD Ports Group are normally dispatched through `_render_port_operator_terminal`, where the radio still contained only Overview and Corporate Tree. `_render_institution_terminal` was also missing the third view.

## Install
Replace deployed `pc_terminal.py` with this file and place `pc_company_network_ui.py` alongside it (or retain the same helper from the previous generic patch). Do not replace `pc_market_lenses.py` or the launcher. Commit/push/redeploy the correct Streamlit repository and use the in-app Refresh database control after deploy.

## Behaviour
All three entity renderer paths now provide Overview, Corporate Tree, Network & Evidence using the same reusable module. The view reads direct canonical links for the selected entity and does not hardcode Noatum or AD Ports names, IDs, metrics or special SQL views. No Supabase schema/data changes.

## Verification
For `?pc_terminal_type=entity&pc_terminal_id=COMP_NOATUM`, confirm three options appear. Repeat for AD Ports, a generic company and an institutional organisation. Select Network & Evidence to check company and asset links. A zero direct asset count for historical COMP_NOATUM is not the Noatum group's 45-asset aggregate; navigate connected branches for their direct links. Python syntax checked; live app not executed here.
