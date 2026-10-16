-- Sulina geographical reference for two connected casualty dossiers.
-- Town reference only, NOT either vessel's incident/strike position.
BEGIN;
UPDATE public.pc_events
SET metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object(
 'geographic_reference',jsonb_build_object(
 'label','Sulina, Tulcea County, Romania — regional reference only',
 'latitude',45.1553,'longitude',29.6546,
 'precision','Sulina town reference; NOT vessel, fire, attack, wreck or casualty position',
 'source_url','https://wiki.openstreetmap.org/wiki/Ro:Romania/Jude%C8%9Bul_Tulcea/Sulina',
 'source_description','OpenStreetMap Sulina locality reference'
 ))
WHERE event_id IN ('PC_BS_SULINA_WINE_TRADER_FIRE_20261015','PC_BS_SULINA_YARA_J_FIRE_20261014');
COMMIT;
SELECT event_id,metadata->'geographic_reference' geographic_reference
FROM public.pc_events WHERE event_id IN ('PC_BS_SULINA_WINE_TRADER_FIRE_20261015','PC_BS_SULINA_YARA_J_FIRE_20261014');
