-- Read-only: discover how event risk tags connect to events.
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema='public'
  AND (table_name ILIKE '%risk_tag%' OR table_name ILIKE '%event_type_link%')
ORDER BY table_name, ordinal_position;
