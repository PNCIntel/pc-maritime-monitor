-- Inspect deployed publication/backup/resolution RPCs; no data changes.
SELECT n.nspname AS schema_name, p.proname AS function_name,
       pg_get_function_identity_arguments(p.oid) AS arguments,
       pg_get_functiondef(p.oid) AS definition
FROM pg_proc p
JOIN pg_namespace n ON n.oid = p.pronamespace
WHERE n.nspname = 'public'
  AND p.proname IN ('pc_v10_backup_staged', 'pc_v10_publish_approved',
                   'pc_resolve_upsert_entity', 'pc_v12_sync_published_links')
ORDER BY p.proname, p.oid;
