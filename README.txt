Power & Corridors — Entity Completion + Live Company Activity

Files:
- pc-power-admin.py  -> Workflow Console v5.6 entity-completion pass
- app.py             -> Trade v3.3.43 live company activity/event-link bridge

What changes:
1. AI Research now has a default-on "Complete discovered entities" second pass.
   It researches assets, terminals, relationships, events, transactions and routes
   around entities found in the first pass instead of stopping at an entity shell.
2. Material source/news developments are explicitly required to become pc_events +
   pc_event_links, so the source activity remains attached to the entity.
3. Trade company profiles now read live pc_event_links directly and project them into
   the existing Event Company / Asset link frames.
4. The News tab now includes canonical linked event/activity coverage even when there
   is no separate legacy News Registry row.

No SQL change is required beyond the already-installed 037/038 workflow patches.
Deploy both files together for the intended behavior.
