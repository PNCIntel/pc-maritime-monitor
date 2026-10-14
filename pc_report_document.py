"""Document-first narrative editing atop existing Report Studio blocks.

Table IDs, rows, positions, and evidence are retained; headings delimit prose.
"""
import re


def manuscript_from_blocks(blocks):
    parts = []
    for block in blocks:
        if block.get("kind") == "Asset table":
            parts.append("<!-- P&C TABLE:" + block["id"] + " -->")
        elif block.get("kind") != "References":
            parts.append("## " + str(block.get("title") or "Untitled").replace("\n", " ").strip()
                         + "\n\n" + str(block.get("body") or "").strip())
    return "\n\n".join(parts).strip()


def apply_manuscript(existing, manuscript):
    """Return (new_blocks, error). Reject missing/duplicated table anchors."""
    from copy import deepcopy
    table_map = {b["id"]: b for b in existing if b.get("kind") == "Asset table"}
    marker = re.compile(r"(?m)^<!-- P&C TABLE:([a-f0-9]{12}) -->\s*$")
    anchors = marker.findall(manuscript)
    if len(anchors) != len(set(anchors)) or set(anchors) != set(table_map):
        return existing, "Every linked evidence table must retain its original marker exactly once."
    tokens = re.split(r"(?m)^(## [^\n]+|<!-- P&C TABLE:[a-f0-9]{12} -->)\s*$", manuscript)
    if tokens[0].strip():
        return existing, "Begin the manuscript with a ## heading (or an existing table marker)."
    original_narratives = [b for b in existing if b.get("kind") not in ("Asset table", "References")]
    result = []
    n = 0
    for pos in range(1, len(tokens), 2):
        head = tokens[pos].strip()
        body = tokens[pos + 1].strip() if pos + 1 < len(tokens) else ""
        if head.startswith("<!-- P&C TABLE:"):
            if body:
                return existing, "Put prose under a ## heading, not directly below a table marker."
            result.append(deepcopy(table_map[head[len("<!-- P&C TABLE:"):-len(" -->")]]))
        else:
            if n < len(original_narratives):
                b = deepcopy(original_narratives[n])
            else:
                from uuid import uuid4
                b = {"id": uuid4().hex[:12], "kind": "Narrative", "preset": "Custom", "rows": []}
            b.update({"kind": "Narrative", "title": head[3:].strip(), "body": body})
            if not b["title"]:
                return existing, "A section heading cannot be empty."
            result.append(b)
            n += 1
    result += [deepcopy(b) for b in existing if b.get("kind") == "References"]
    return result, None
