# Targeted Fujairah / security lens repair

Replace **only** `pc_market_lenses.py` in a test branch. The existing `pc_terminal.py` and all other dependencies are preserved.

- Expand infrastructure using explicit `pc_terminal_details.parent_port_asset_id` links alongside the pre-existing dossier.
- Resolve facility events from both `pc_event_asset_links` and `pc_event_links` plus existing event accessor.
- Filter security-related events by existing classifications.
- Do not infer attacks on a location simply because incidents occurred nearby, or a company operates a facility.
- Warn of missing direct link coverage rather than claiming no events exist.

**Not live tested.** Assumes the existing table and column names previously observed: `pc_event_asset_links(asset_id,event_id)`, `pc_terminal_details(parent_port_asset_id,asset_id)`. Database permissions or schema drift can still affect results.

## Validation SQL
```sql
SELECT 'terminal_details' AS kind, count(*) AS n FROM public.pc_terminal_details WHERE parent_port_asset_id = 'PORT_UAE_PORT_OF_FUJAIRAH'
UNION ALL
SELECT 'event_asset_links',count(*) FROM public.pc_event_asset_links WHERE asset_id='PORT_UAE_PORT_OF_FUJAIRAH'
UNION ALL
SELECT 'event_links',count(*) FROM public.pc_event_links WHERE linked_id='PORT_UAE_PORT_OF_FUJAIRAH';
```

A count of zero for direct event links does not prove missing regional events; review event-to-asset linkage separately.
