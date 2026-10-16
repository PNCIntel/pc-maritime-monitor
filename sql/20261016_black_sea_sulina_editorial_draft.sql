-- Black Sea Sulina analytical repair | DRAFT, NOT approved | 16 Oct 2026
-- Adds meaningful connected-event dossier content without manufacturing a continuing threat score.
BEGIN;
UPDATE public.pc_events e SET metadata=coalesce(e.metadata,'{}'::jsonb) ||
jsonb_build_object('editorial_profile',jsonb_build_object(
 'review_status','draft_for_analyst_review','significance','major',
 'current_threat','not_assessed','current_threat_label','Not assessed — ongoing vessel-specific threat not established',
 'assessed_at','2026-10-16T09:56:00+04:00',
 'evidence_confidence','Moderate — reported official casualty response; strike mechanism and attribution unconfirmed',
 'significance_rationale','Two fires involving merchant tankers near Romania’s Sulina approaches across successive reporting dates, including a search-and-rescue emergency, warrant heightened scrutiny of the Black Sea–Danube access corridor. Regional importance does not itself establish a continuing threat, an attacker, a port closure or verified cargo disruption.',
 'analysis',CASE WHEN e.event_id='PC_BS_SULINA_YARA_J_FIRE_20261014' THEN
 'YARA J (IMO 9221803) was reported to have caught fire near Sulina; all 17 aboard were subsequently reported safe after the blaze was extinguished. A suspected drone impact was reported by the crew, but official inquiry into the cause remained material. The incident is a distinct vessel casualty, not proof of coordinated attacks with WINE TRADER. The vessel registry names Yara Shipping Co Inc in ownership/management roles, subject to registry reconciliation. No verified berth, terminal or operator outage follows from these reports.'
 ELSE
 'WINE TRADER (IMO 8808707) caught fire near Sulina with 12 aboard. Reported rescue counts changed from four rescued/eight missing to five rescued/seven missing; treat this as a sequence of official/reporting updates, not two independent casualties. The urgent issue is the search-and-rescue outcome and any verified spill, navigational obstruction or restriction in the Sulina approaches. Registry reporting identifies Waterfalls Co Ltd as registered owner and Sicilship SRL as ISM manager; this is not proof of ultimate beneficial ownership. Cause and perpetrator remain unconfirmed.'
 END,
 'outlook','Do not extrapolate a closure of Sulina or the wider Danube corridor. The assessment changes materially if Romanian maritime authorities confirm strike forensics, publish navigational restrictions, report pollution or floating hazards, or revise crew-rescue status. Independent evidence of additional vessel incidents would support evaluating a broader pattern; proximity alone does not establish common attribution.',
 'monitoring',jsonb_build_array(
 'Search and rescue: seek dated Romanian Naval Authority/MRCC confirmation of persons rescued, still missing, injured or deceased, particularly WINE TRADER.',
 'Causation and attribution: distinguish official forensic findings from crew suspicion and unattributed military/security assessments; do not assign an attacker prematurely.',
 'Navigation: inspect Romanian maritime and Danube/Sulina navigation notices for vessel traffic restrictions, pilotage disruption, hazards or changes to anchorage procedures.',
 'Environmental exposure: confirm whether either tanker released cargo or bunkers, whether pollution response was activated, and whether local waterway operations were affected.',
 'Fleet and counterparties: reconcile IMO-based registered owner, technical/ISM and commercial manager identities against dated authoritative registry extracts before asserting corporate control.',
 'Corroboration: monitor separate fires or strikes affecting Black Sea merchant shipping, maintaining distinct event and casualty timelines.'
 ),
 'source_urls',coalesce(e.metadata->'source_urls','[]'::jsonb),
 'report_date_qualification','Event dates are day-level; incident clock times and precise strike locations unverified',
 'review_note','DRAFT editorial assessment. Assessed-at is preparation timestamp, not approval timestamp.'
))
WHERE e.event_id IN ('PC_BS_SULINA_YARA_J_FIRE_20261014','PC_BS_SULINA_WINE_TRADER_FIRE_20261015')
AND coalesce(e.metadata->'editorial_profile'->>'review_status','') <> 'approved';
COMMIT;
SELECT event_id,metadata->'editorial_profile'->>'review_status' review_status,
metadata->'editorial_profile'->>'significance' significance,
metadata->'editorial_profile'->>'current_threat' current_threat,
metadata->'editorial_profile'->>'assessed_at' prepared_at,
metadata->'editorial_profile'->>'evidence_confidence' evidence_confidence
FROM public.pc_events
WHERE event_id IN ('PC_BS_SULINA_YARA_J_FIRE_20261014','PC_BS_SULINA_WINE_TRADER_FIRE_20261015');
