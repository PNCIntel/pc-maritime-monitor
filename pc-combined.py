"""Power & Corridors combined client application.

Provides one Streamlit deployment for clients entitled to both P&C Trade and
P&C Intelligence while keeping the two existing applications independently
maintainable.  The selected child app is executed from its own source file;
only its st.set_page_config call is removed because this shell owns page setup.

The underlying data model remains shared (Supabase/PostgreSQL with Excel
fallback during migration).
"""
from __future__ import annotations

import ast
import os
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
TRADE_APP = ROOT / "app.py"
INTELLIGENCE_APP = ROOT / "pc_intelligence_app.py"

st.set_page_config(
    page_title="Power & Corridors · Trade + Intelligence",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _remove_page_config(tree: ast.AST) -> ast.AST:
    """Remove top-level st.set_page_config(...) calls from a child app AST."""
    if not isinstance(tree, ast.Module):
        return tree
    cleaned = []
    for node in tree.body:
        remove = False
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            fn = node.value.func
            if (
                isinstance(fn, ast.Attribute)
                and fn.attr == "set_page_config"
                and isinstance(fn.value, ast.Name)
                and fn.value.id == "st"
            ):
                remove = True
        if not remove:
            cleaned.append(node)
    tree.body = cleaned
    ast.fix_missing_locations(tree)
    return tree


def _run_child(path: Path) -> None:
    """Execute one existing Streamlit app without duplicating its page config."""
    if not path.exists():
        st.error(f"Application file is missing: {path.name}")
        st.stop()

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    tree = _remove_page_config(tree)
    code = compile(tree, filename=str(path), mode="exec")

    # Give the child the same semantics it would have when launched directly.
    namespace = {
        "__name__": "__main__",
        "__file__": str(path),
        "__package__": None,
    }
    exec(code, namespace, namespace)


# Product selection can be deep-linked with ?product=trade or ?product=intelligence.
requested = ""
try:
    requested = str(st.query_params.get("product", "") or "").strip().lower()
except Exception:
    try:
        qp = st.experimental_get_query_params()
        requested = str((qp.get("product") or [""])[0]).strip().lower()
    except Exception:
        requested = ""

labels = ["P&C Trade", "P&C Intelligence"]
default_idx = 1 if requested in {"intelligence", "intel", "security"} else 0

with st.sidebar:
    st.markdown("### Power & Corridors")
    st.caption("Combined client access")
    product = st.radio(
        "Product",
        labels,
        index=default_idx,
        key="pc_combined_product",
    )
    appearance = st.radio(
        "Appearance",
        ["Dark","Light"],
        horizontal=True,
        key="pc_combined_appearance",
    )
    st.session_state["pc_trade_appearance"] = appearance
    st.session_state["pc_intel_appearance"] = appearance
    if st.button("↻ Refresh database", use_container_width=True, key="pc_combined_refresh_database"):
        st.cache_data.clear()
        try:
            st.cache_resource.clear()
        except Exception:
            pass
        st.rerun()
    st.caption("Refresh after Power Admin applies canonical changes.")
    st.divider()

slug = "intelligence" if product == "P&C Intelligence" else "trade"
try:
    if str(st.query_params.get("product", "") or "") != slug:
        st.query_params["product"] = slug
except Exception:
    pass

# Optional deployment-level feature flags.  They are deliberately permissive
# by default; Supabase product entitlements remain the authoritative gate once
# PC_REQUIRE_AUTH=true.
if product == "P&C Trade":
    if os.getenv("PC_COMBO_ENABLE_TRADE", "true").lower() != "true":
        st.error("P&C Trade is disabled for this deployment.")
        st.stop()
    _run_child(TRADE_APP)
else:
    if os.getenv("PC_COMBO_ENABLE_INTELLIGENCE", "true").lower() != "true":
        st.error("P&C Intelligence is disabled for this deployment.")
        st.stop()
    _run_child(INTELLIGENCE_APP)
