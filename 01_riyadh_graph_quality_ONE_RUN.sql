-- P&C Riyadh canonical airport graph quality repair | 2026-10-12
-- Rerunnable; does not merge assets, overwrite operational status, or fabricate impacts.
BEGIN;
DO $fix$
DECLARE v_parent constant text := 'PC_SA26_AP_OERK';
        v_dup constant text := 'ASSET_8DCF5F65A5BB6AAE2FC4';
        v_child text;
BEGIN
 IF NOT EXISTS (SELECT 1 FROM public.pc_assets WHERE asset_id=v_parent AND name='King Khalid International Airport' AND lower(asset_type)='airport') THEN
   RAISE EXCEPTION 'Canonical OERK airport absent or renamed; no changes made';
 END IF;
 IF NOT EXISTS (SELECT 1 FROM public.pc_events WHERE event_id='EV_SA_RUH_AIRLINE_DISRUPTION_20261012') THEN
   RAISE EXCEPTION 'Operational event absent; no changes made';
 END IF;
 -- Maintain the one confirmed graph link between the update and the operational airport.
 INSERT INTO public.pc_event_asset_links(event_id,asset_id,relation_type,impact_status,source_id,metadata)
 SELECT 'EV_SA_RUH_AIRLINE_DISRUPTION_20261012',v_parent,'exposed','reported',
        'SRC_PC_AM_SA_20261012',jsonb_build_object('specific_relationship','airport_closure_and_airline_schedule_disruption','not_a_new_strike',true,'stewardship_batch','PC_RUH_VIEW_FIX_20261012')
 WHERE NOT EXISTS (SELECT 1 FROM public.pc_event_asset_links WHERE event_id='EV_SA_RUH_AIRLINE_DISRUPTION_20261012' AND asset_id=v_parent);
 -- Stewardship annotation only: duplicate-looking identity has not been merged/repointed.
 IF EXISTS (SELECT 1 FROM public.pc_assets WHERE asset_id=v_dup AND name='King Khalid International Airport') THEN
   UPDATE public.pc_assets SET metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('canonical_review_20261012',jsonb_build_object(
    'candidate_survivor',v_parent,'identity_status','possible_duplicate_under_review',
    'same_aerodrome_not_verified_by_db_key',true,'merged',false,'link_repointing_done',false))
   WHERE asset_id=v_dup;
 END IF;
 UPDATE public.pc_assets SET metadata=coalesce(metadata,'{}'::jsonb)||jsonb_build_object('dossier_reference_20261012',jsonb_build_object(
  'published_airport_key','OERK','event_link_table','pc_event_asset_links',
  'operational_current_state_not_derived_from_static_asset_status',true,
  'date_of_notam_expiry_not_a_reopening_confirmation',true))
 WHERE asset_id=v_parent;
END $fix$;
COMMIT;
SELECT jsonb_build_object('batch','PC_RUH_VIEW_FIX_20261012',
 'airport_id','PC_SA26_AP_OERK',
 'linked_airport_records',(SELECT count(DISTINCT event_id) FROM public.pc_event_asset_links WHERE asset_id='PC_SA26_AP_OERK'),
 'update_asset_links',(SELECT count(*) FROM public.pc_event_asset_links WHERE event_id='EV_SA_RUH_AIRLINE_DISRUPTION_20261012' AND asset_id='PC_SA26_AP_OERK'),
 'related_terminal_4_links',(SELECT count(*) FROM public.pc_event_asset_links WHERE asset_id='PC_SA26_FAC_OERK_T4'),
 'alternate_record_still_present',(SELECT EXISTS(SELECT 1 FROM public.pc_assets WHERE asset_id='ASSET_8DCF5F65A5BB6AAE2FC4')),
 'review_not_merge',true,
 'next_step','Redeploy three existing modules plus new pc_airport_event_dossier.py') AS report;
