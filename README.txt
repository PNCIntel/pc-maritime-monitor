P&C Intelligence v3.3.41 — Alert Card HTML Rendering Fix

Replace pc_intelligence_app.py only.

Fixes:
- Raw <div class="pc-card-impact"> markup rendering as code on alert cards.
- Uses single-line card HTML to avoid Markdown code-block parsing.
- Escapes dynamic event text safely.
- Uses Trade / commercial impact label when that fallback field is displayed.

No SQL changes required.
