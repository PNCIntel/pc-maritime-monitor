P&C Intelligence v3.3.40 - Clean Alert Cards

Replace:
  pc_intelligence_app.py

Changes:
- Removes literal NaN / None from alert cards.
- Omits empty description/impact blocks instead of displaying placeholders.
- Falls back to Trade / Commercial Impact when Operational Impact is absent.
- Formats event dates as readable dates.
- Humanizes event types such as PIPELINE_ATTACK -> Pipeline attack.
- Retains the v3.3.39 live-canonical Supabase alert/event bridge.
