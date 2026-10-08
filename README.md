# Power & Corridors — Seven Applications Foundation

One Supabase data model; seven Streamlit entry points. No migrations or database writes.

## Existing application entry points (preserved)

- PC_Trade_Regional_Dashboard.py → pc_market_lenses.render_market_terminal("trade")
- PC_Strategic_Industries_app.py → pc_market_lenses.render_market_terminal("strategic")
- PC_Sanctions_app.py → pc_terminal.render_terminal("sanctions")
- PC_Intelligence_Regional_Dashboard.py → pc_terminal.render_terminal("intelligence")

These require the deployment's original `pc_market_lenses.py` and `pc_terminal.py`, which were not among the uploads. **Their internal UI labels have not yet been modified.**

## New application foundations

- PC_Capital_Ownership_app.py
- PC_Commodities_Resources_app.py
- PC_Markets_Freight_app.py

Each offers business terminology, common navigation, responsive Streamlit page sections and optional read-only global search against the existing `pc_entities`, `pc_assets` and `pc_mobile_assets` via `supabase-py`. These are starter shells, **not completed market dashboards**. No invented market metrics or ownership links.

## Integration

1. Add `pc_portfolio.py` plus seven entry points to your application repository. **Back up the existing four launcher files before replacing them.** Keep your existing renderer modules intact.
2. For the three new market apps, configure `SUPABASE_URL` and `SUPABASE_ANON_KEY` in Streamlit secrets; enable the applicable RLS policies. Do not place privileged service-role credentials in a public UI.
3. Install `streamlit` and `supabase` in the application environment (e.g. requirements.txt).
4. Start each entry point independently using `streamlit run <filename>.py`; configure each deployment entry point accordingly.
5. To complete the business-facing UI redesign of existing dashboards, supply `pc_market_lenses.py` and `pc_terminal.py`, plus their imported UI helpers. The present launcher files contain no actual search/profile renderer implementation.

## Design rules

- Show user-friendly names, hide canonical IDs by default.
- Distinguish fixed facilities, moving assets and companies.
- Preserve source URLs and observed-vs-effective date semantics.
- Use dedicated asset-specific profile sections: ports, airports, rail terminals, industrial sites, vessels and aircraft.
- Respect separate jurisdictions and ownership/operator/charter/service-provider roles.
- Share UI and model, but give each market a meaningful specialist landing page.
