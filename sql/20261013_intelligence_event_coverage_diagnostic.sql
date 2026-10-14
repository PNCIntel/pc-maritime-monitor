-- Read-only reconciliation: run in Supabase SQL editor.
-- No inserts, updates, schema changes or publication overrides.
-- First: total canonical events versus delivery projections.
SELECT 'pc_events' AS source, count(*) AS n FROM public.pc_events
UNION ALL SELECT 'pc_delivery_objects (event)', count(*) FROM public.pc_delivery_objects WHERE object_type='event'
UNION ALL SELECT 'pc_app_security_records (event)', count(*) FROM public.pc_app_security_records WHERE object_type='event'
UNION ALL SELECT 'pc_app_trade_records (event)', count(*) FROM public.pc_app_trade_records WHERE object_type='event';

-- Target event reconciliation: inspect IDs and canonical raw fields rather than guessing dates/types.
WITH candidates AS (
 SELECT e.event_id::text AS event_id, e.title::text AS title, to_jsonb(e) AS canonical
 FROM public.pc_events e
 WHERE (e.title || ' ' || to_jsonb(e)::text) ~* '(black sea|turk(ish|ey|iye)|hmm|tanker|hormuz|containership|port of refuge)'
)
SELECT c.event_id,c.title,
       s.object_id IS NOT NULL AS in_security_delivery,
       t.object_id IS NOT NULL AS in_trade_delivery,
       s.section AS security_section,t.section AS trade_section,
       c.canonical
FROM candidates c
LEFT JOIN public.pc_app_security_records s ON s.object_type='event' AND s.object_id=c.event_id
LEFT JOIN public.pc_app_trade_records t ON t.object_type='event' AND t.object_id=c.event_id
ORDER BY c.title,c.event_id;

-- Events unexpectedly excluded from the security delivery projection.
SELECT e.event_id,e.title,to_jsonb(e) AS canonical
FROM public.pc_events e
WHERE NOT EXISTS (
 SELECT 1 FROM public.pc_app_security_records s
 WHERE s.object_type='event' AND s.object_id=e.event_id::text
)
ORDER BY e.title
LIMIT 100;

-- Note: these delivery views do not establish what the separate
-- 'Global Operating Picture' screen actually queries. If all target
-- records occur above, inspect its screen-level publication, editorial,
-- date, pagination and link joins. Preserve canonical event IDs.
