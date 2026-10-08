"""P&C seven-market presentation layer. Does not change the Supabase schema.

Existing Trade/Strategic/Sanctions/Intelligence renderers are preserved.
Capital/Commodities/Markets have a working read-only starter view when the
Supabase Python client and Streamlit secrets are configured.
"""
from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
import streamlit as st

@dataclass(frozen=True)
class Market:
    label: str
    purpose: str
    focus: tuple[str, ...]
    source_tables: tuple[str, ...]
    renderer: str | None = None
    lens: str | None = None

MARKETS = {
    "trade": Market("Trade & Logistics", "Transport networks, cargo flows and commercial operations", ("Infrastructure", "Transport connections", "Companies & operations", "Commercial developments"), ("pc_assets", "pc_mobile_assets", "pc_entities", "pc_transport_services", "pc_events"), "pc_market_lenses:render_market_terminal", "trade"),
    "strategic": Market("Strategic Industries", "Industrial capability, investment and supply chains", ("Industrial facilities", "Production & capacity", "Suppliers & contracts", "Investment & projects"), ("pc_assets", "pc_project_details", "pc_entities", "pc_contracts"), "pc_market_lenses:render_market_terminal", "strategic"),
    "sanctions": Market("Sanctions & Compliance", "Sanctions, counterparties and regulatory exposure", ("Sanctions screening", "Ownership networks", "Vessels & aircraft", "Sources & decisions"), ("pc_entities", "pc_mobile_assets", "pc_events"), "pc_terminal:render_terminal", "sanctions"),
    "intelligence": Market("Security & Disruptions", "Incidents, risk and operational consequences", ("Incidents", "Affected facilities", "Affected fleets", "Commercial exposure"), ("pc_events", "pc_event_evidence", "pc_event_asset_links", "pc_assets", "pc_mobile_assets"), "pc_terminal:render_terminal", "intelligence"),
    "capital": Market("Capital & Ownership", "Investment, acquisitions and corporate ownership over time", ("Company profiles", "Ownership & shareholders", "Acquisitions & concessions", "Investment history"), ("pc_entities", "pc_company_relationships", "pc_contracts", "pc_contract_participants", "pc_project_details")),
    "commodities": Market("Commodities & Resources", "Energy, food, minerals and commodity supply chains", ("Energy", "Agriculture & food", "Minerals & materials", "Trade & infrastructure"), ("pc_assets", "pc_entities", "pc_port_metrics", "pc_events", "pc_project_details")),
    "markets": Market("Markets & Freight", "Freight, capacity, rates and transport-market indicators", ("Freight indicators", "Transport services", "Capacity", "Market developments"), ("pc_port_metrics", "pc_transport_services", "pc_events", "pc_assets")),
}

# Shared business terminology; technical identifiers remain in backend only.
BUSINESS_LABELS = {
    "Global Command Bar": "Global Search",
    "Selected Canonical Context": "Overview",
    "Node Profile": "Details",
    "Ecosystem Nodes": "Connected Infrastructure",
    "Operators / Owners": "Companies & Ownership",
    "Connected Companies & Services": "Companies & Operations",
    "Spatial & Local System": "Location & Connections",
    "Corridors, Routes & Services": "Trade & Transport Connections",
    "Capacity, Projects & Investment": "Capacity & Investment",
    "Current Developments": "Latest Activity",
    "Evidence & Documents": "Sources & Documents",
    "History & Throughput": "Performance & History",
}

OBJECT_TYPES = {
    "pc_assets": "Infrastructure & Facilities",
    "pc_mobile_assets": "Vessels, Aircraft & Fleets",
    "pc_entities": "Companies & Organisations",
}


def page_setup(market_key: str) -> None:
    market = MARKETS[market_key]
    st.set_page_config(page_title=f"P&C | {market.label}", page_icon="◈", layout="wide", initial_sidebar_state="expanded")
    st.markdown("""<style>
      .block-container {padding-top: 1.7rem; max-width: 1480px;}
      h1,h2,h3 {letter-spacing:-.018em;}
      [data-testid='stMetricValue'] {font-size:1.55rem;}
      div[data-testid='stDataFrame'] {border-radius:9px;}
      </style>""", unsafe_allow_html=True)


def render_existing(market_key: str) -> None:
    market = MARKETS[market_key]
    if not market.renderer:
        raise ValueError(f"Market {market_key} does not have a legacy renderer")
    mod, fn = market.renderer.split(":", 1)
    try:
        render = getattr(import_module(mod), fn)
    except (ImportError, AttributeError) as exc:
        st.error(f"The existing {market.label} renderer is not installed in this deployment.")
        st.caption(f"Required shared module: {mod}.py. The database has not been modified.")
        st.exception(exc)
        return
    render(market.lens)


def _supabase_client():
    """Read-only views require a Supabase key constrained by database RLS."""
    try:
        from supabase import create_client
        cfg = st.secrets
        url = cfg.get('SUPABASE_URL') or cfg.get('supabase_url')
        key = cfg.get('SUPABASE_ANON_KEY') or cfg.get('supabase_anon_key')
        return create_client(url, key) if url and key else None
    except (ImportError, KeyError, FileNotFoundError):
        return None


def _search(client, table: str, text: str, max_rows: int = 30):
    id_col = {"pc_entities": "entity_id", "pc_assets": "asset_id", "pc_mobile_assets": "mobile_asset_id"}[table]
    response = client.table(table).select(f"{id_col},name").ilike("name", f"%{text}%").limit(max_rows).execute()
    return response.data or []


def render_foundation(market_key: str) -> None:
    market = MARKETS[market_key]
    st.title(market.label)
    st.caption(f"POWER & CORRIDORS  /  {market.purpose}")
    st.write("Explore the same global company, infrastructure and fleet records through a specialist business lens.")
    with st.sidebar:
        st.subheader("Power & Corridors")
        st.caption(market.label)
        st.markdown("**Areas of focus**")
        for item in market.focus:
            st.write("•", item)
        st.caption("One underlying database · seven market views")
    st.subheader("Global Search")
    query = st.text_input("Search companies, infrastructure or fleets", placeholder="e.g., Fujairah, ADNOC, Rotterdam, Odesa", key=f"search_{market_key}")
    client = _supabase_client()
    if not client:
        st.info("Connect the existing Supabase project via SUPABASE_URL and SUPABASE_ANON_KEY in Streamlit secrets to enable live read-only search.")
    elif len(query.strip()) >= 2:
        tabs = st.tabs(tuple(OBJECT_TYPES.values()))
        for tab, (table, label) in zip(tabs, OBJECT_TYPES.items()):
            with tab:
                try:
                    results = _search(client, table, query.strip())
                    if results:
                        # Internal IDs are retained for joining, not displayed as UI labels.
                        st.dataframe([{"Name": r.get('name', '')} for r in results], use_container_width=True, hide_index=True)
                        st.caption(f"{len(results)} matches in {label.lower()}. Detailed profiles follow the existing model's access rules.")
                    else:
                        st.caption("No matches in this category.")
                except Exception as exc:
                    st.warning(f"Unable to query {label.lower()} with the configured permissions: {exc}")
    st.divider()
    st.subheader("Explore this market")
    cols = st.columns(2)
    for i, heading in enumerate(market.focus):
        with cols[i % 2]:
            with st.container(border=True):
                st.markdown(f"**{heading}**")
                st.caption("Uses established P&C objects and time-aware commercial relationships; specialist profile views require the shared query/render modules.")
    with st.expander("Data scope and methodology"):
        st.write("Core model: fixed infrastructure in pc_assets, mobile assets in pc_mobile_assets, organisations in pc_entities; specialist histories in existing relationship, project, contract and event tables.")
        st.write("A dated source observation is not automatically an effective ownership date. Missing data is not presented as zero or as no exposure.")
