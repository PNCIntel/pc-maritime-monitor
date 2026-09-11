"""OpenAI research helper for the P&C controlled ingestion workflow.

AI output is research/staging material only. This module never writes directly
to canonical production tables.

Required:
    OPENAI_API_KEY

Optional:
    OPENAI_MODEL        default: gpt-5.6-luna
"""
from __future__ import annotations

import json
import os

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


def _secret(name: str, default: str = "") -> str:
    value = os.getenv(name, default)
    if value:
        return str(value)

    try:
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name])

        if "openai" in st.secrets:
            mapping = {
                "OPENAI_API_KEY": "api_key",
                "OPENAI_MODEL": "model",
            }
            key = mapping.get(name)
            if key and key in st.secrets["openai"]:
                return str(st.secrets["openai"][key])
    except Exception:
        pass

    return default


def model_name() -> str:
    return _secret("OPENAI_MODEL", "gpt-5.6-luna")


def configured() -> bool:
    return bool(OpenAI and _secret("OPENAI_API_KEY"))


def research(
    prompt: str,
    product_context: str = "TRADE",
    use_web: bool = True,
    output_contract: str | None = None,
) -> dict:
    """Run research and return JSON-compatible output.

    The function deliberately does not apply any database writes.
    """
    if not configured():
        raise RuntimeError("OPENAI_API_KEY is not configured.")

    client = OpenAI(api_key=_secret("OPENAI_API_KEY"))

    contract = output_contract or (
        "Return a JSON object with: proposed_entities, proposed_assets, "
        "proposed_relationships, proposed_events, sources, conflicts, notes."
    )

    instructions = f"""
You are the internal Power & Corridors research engine.

Product context: {product_context}

Rules:
- Research and extract evidence; never claim a database change has been applied.
- Do not invent identifiers, ownership, capacity, dates, IMO numbers, locations,
  sanctions, investment values, or relationships.
- Prefer primary/official sources, company filings/releases, regulators, port or
  government authorities, and other high-quality public sources.
- Distinguish confirmed facts from inference.
- For P&C Intelligence, exclude routine corporate developments unless they
  create a security, operational, sanctions, regulatory, supply-chain, or
  infrastructure consequence.
- For P&C Trade, commercial, investment, capacity, ownership, route and asset
  developments are in scope.
- Preserve source URLs for every proposed record.
- If evidence is insufficient, omit the field or proposal rather than guessing.

Output contract:
{contract}

Return JSON only.
""".strip()

    tools = [{"type": "web_search"}] if use_web else []

    resp = client.responses.create(
        model=model_name(),
        instructions=instructions,
        input=prompt,
        tools=tools,
    )

    text = getattr(resp, "output_text", "") or ""

    try:
        parsed = json.loads(text)
    except Exception:
        # Keep raw output for analyst review instead of discarding it.
        parsed = {"raw_output": text}

    parsed["_response_id"] = getattr(resp, "id", None)
    parsed["_model"] = model_name()
    return parsed
