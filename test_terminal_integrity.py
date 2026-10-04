"""Static integrity checks for the four P&C Streamlit terminals.

Run with:
    python test_terminal_integrity.py

These checks are intentionally dependency-light: they parse source files without importing
Streamlit or connecting to Supabase, so they catch refactor regressions before deployment.
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parent

ENTRYPOINTS={
    "PC_Trade_Regional_Dashboard.py":"trade",
    "PC_Intelligence_Regional_Dashboard.py":"intelligence",
    "PC_Sanctions_app.py":"sanctions",
    "PC_Strategic_Industries_app.py":"strategic",
}

SHARED=[
    "pc_terminal.py",
    "pc_report_studio.py",
    "pc_sanctions_report.py",
    "pc_report_ai.py",
]

REQUIRED_TERMINAL_HELPERS={
    "_context_record",
    "_entity_identity_bundle",
    "_multi_filtered_rows",
    "_event_source_urls",
    "_indexed_search",
    "_indexed_links",
    "_render_daily_brief",
    "_render_event_rows",
    "_render_mobile_asset_terminal",
    "_render_port_operator_terminal",
    "_render_spatial_pane",
    "_render_trade_home",
    "_render_intelligence_home",
    "_render_sanctions_home",
    "_render_strategic_home",
    "render_terminal",
}


def parse(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"),filename=str(path))


def defined_functions(tree: ast.AST) -> set[str]:
    return {n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}


def underscore_calls(tree: ast.AST) -> set[str]:
    out=set()
    for n in ast.walk(tree):
        if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id.startswith("_"):
            out.add(n.func.id)
    return out


def test_entrypoints() -> list[str]:
    errors=[]
    for name,lens in ENTRYPOINTS.items():
        p=ROOT/name
        if not p.exists():
            errors.append(f"Missing entrypoint: {name}")
            continue
        tree=parse(p)
        found=False
        for n in ast.walk(tree):
            if not isinstance(n,ast.Call) or not isinstance(n.func,ast.Name):
                continue
            if n.func.id!="render_terminal":
                continue
            if n.args and isinstance(n.args[0],ast.Constant) and n.args[0].value==lens:
                found=True
        if not found:
            errors.append(f"{name} does not call render_terminal({lens!r})")
    return errors


def test_shared_modules() -> list[str]:
    errors=[]
    for name in SHARED:
        p=ROOT/name
        if not p.exists():
            errors.append(f"Missing shared module: {name}")
            continue
        try:
            tree=parse(p)
        except SyntaxError as exc:
            errors.append(f"{name}: SyntaxError: {exc}")
            continue

        defs=defined_functions(tree)
        calls=underscore_calls(tree)
        missing=sorted(x for x in calls if x not in defs and x not in {"__import__"})
        if missing:
            errors.append(f"{name}: undefined local helper call(s): {', '.join(missing)}")

        if name=="pc_terminal.py":
            absent=sorted(REQUIRED_TERMINAL_HELPERS-defs)
            if absent:
                errors.append(f"{name}: required helper(s) missing: {', '.join(absent)}")
    return errors


def main() -> int:
    errors=test_entrypoints()+test_shared_modules()
    if errors:
        print("TERMINAL INTEGRITY CHECK FAILED")
        for e in errors:
            print(" -",e)
        return 1
    print("TERMINAL INTEGRITY CHECK PASSED")
    print("Checked entrypoints:",", ".join(ENTRYPOINTS))
    print("Checked shared modules:",", ".join(SHARED))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
