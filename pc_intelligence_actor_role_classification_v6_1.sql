
-- ============================================================================
-- P&C Intelligence — Event Actor Role Classification v6.1
-- Machine-assisted role refinement from supplied event title/description only
-- 2026-09-15
--
-- IMPORTANT:
--   - Updates role / attribution / confidence for the 25 current backfill links.
--   - Leaves analyst_reviewed = false.
--   - Records role_review_state = machine_assisted_proposed in metadata.
--   - Does NOT invent source_id values.
--   - Ambiguous attribution remains "associated", "reported", or "claimed".
-- Attribution values conform to existing CHECK constraint:
--   confirmed, claimed, assessed, probable, possible, suspected,
--   associated, context_only, disputed, unknown
--
-- v6.1 maps prior invalid draft values as follows:
--   reported   -> assessed
--   attributed -> assessed
--   declared   -> assessed
--   contextual-only cases -> context_only
-- ============================================================================

begin;

-- --------------------------------------------------------------------------
-- Optional vocabulary table for consistent UI/filtering.
-- No FK/check constraint is imposed yet so legacy roles are not broken.
-- --------------------------------------------------------------------------

create table if not exists public.pc_actor_role_types (
    actor_role text primary key,
    label text not null,
    description text,
    active boolean not null default true,
    sort_order integer,
    created_at timestamptz not null default now()
);

insert into public.pc_actor_role_types (actor_role, label, description, sort_order)
values
    ('initiator', 'Initiator', 'Actor reported or attributed as carrying out the event/action.', 10),
    ('directing_actor', 'Directing Actor', 'Actor reported as directing or controlling another operational actor.', 20),
    ('territorial_controller', 'Territorial Controller', 'Actor reported as seizing, holding, or exercising control over territory or a strategic location.', 30),
    ('threat_actor', 'Threat Actor', 'Actor issuing or maintaining a threat, blockade, targeting warning, or coercive posture.', 40),
    ('target', 'Target', 'Actor, force, position, or organisation targeted by the event.', 50),
    ('negotiating_party', 'Negotiating Party', 'Actor participating in a negotiation, peace process, or political-security mechanism.', 60),
    ('disarmament_subject', 'Disarmament Subject', 'Actor whose forces, camps, weapons, or positions are subject to disarmament or demobilisation measures.', 70),
    ('affected_actor', 'Affected Actor', 'Actor materially affected by a policy, disarmament effort, strike, or other development.', 80),
    ('claimant', 'Claimant', 'Actor claiming responsibility or claiming to have targeted an asset, without independent attribution implied.', 90),
    ('contextual_actor', 'Contextual Actor', 'Actor referenced as material context but not established as initiator, target, or controlling actor.', 100)
on conflict (actor_role) do update
set label = excluded.label,
    description = excluded.description,
    sort_order = excluded.sort_order,
    active = true;

-- --------------------------------------------------------------------------
-- Helper macro pattern:
-- metadata is preserved and extended; analyst_reviewed remains false.
-- --------------------------------------------------------------------------

-- Ansar Allah — alert lifted; actor is context from prior attacks.
update public.pc_event_actor_links
set actor_role = 'contextual_actor',
    attribution_status = 'context_only',
    confidence = 'high',
    link_basis = 'Event states Saudi alerts were linked to earlier Houthi attacks; actor is contextual to the all-clear rather than the initiator of the all-clear.',
    metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'role_review_version','actor_role_v6_1',
        'role_review_state','machine_assisted_proposed',
        'role_review_basis','title_description'
    ),
    updated_at = now()
where event_actor_link_id = 'b227a458-f76d-497c-a946-2921148eaea8';

-- Ansar Allah — territorial expansion/control.
update public.pc_event_actor_links
set actor_role = 'territorial_controller',
    attribution_status = 'assessed',
    confidence = 'high',
    link_basis = 'Title and description describe Houthi advances and expanded control along western Yemen, including Perim Island.',
    metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'role_review_version','actor_role_v6_1','role_review_state','machine_assisted_proposed','role_review_basis','title_description'
    ),
    updated_at = now()
where event_actor_link_id = 'a700f46d-85fc-456f-8130-caf9a1e3964a';

-- Ansar Allah — blockade is the causal threat context for impaired Yanbu flows.
update public.pc_event_actor_links
set actor_role = 'threat_actor',
    attribution_status = 'assessed',
    confidence = 'high',
    link_basis = 'Description attributes reduced Yanbu loadings and routing effects to the Houthi blockade.',
    metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'role_review_version','actor_role_v6_1','role_review_state','machine_assisted_proposed','role_review_basis','title_description'
    ),
    updated_at = now()
where event_actor_link_id = 'cdbd607b-2630-4127-b65e-7b08aa3e1217';

-- Ansar Allah — missile/drone strikes attributed by Saudi authorities.
update public.pc_event_actor_links
set actor_role = 'initiator',
    attribution_status = 'assessed',
    confidence = 'high',
    link_basis = 'Saudi authorities said Houthi ballistic missiles and drones targeted Khamis Mushait, Abha and Taif.',
    metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'role_review_version','actor_role_v6_1','role_review_state','machine_assisted_proposed','role_review_basis','title_description'
    ),
    updated_at = now()
where event_actor_link_id = 'b386a89f-66c9-460d-93c0-3935ac3fc8b7';

-- Ansar Allah — reported capture/control of Mokha and Mayun/Perim.
update public.pc_event_actor_links
set actor_role = 'territorial_controller',
    attribution_status = 'assessed',
    confidence = 'high',
    link_basis = 'AP reporting in the event description states Houthi forces captured Mokha and an island in Bab el-Mandeb.',
    metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'role_review_version','actor_role_v6_1','role_review_state','machine_assisted_proposed','role_review_basis','title_description'
    ),
    updated_at = now()
where event_actor_link_id = '91760593-0449-4d83-9ff8-4967aba80a1e';

-- Ansar Allah — title-only reported capture; retain medium confidence.
update public.pc_event_actor_links
set actor_role = 'territorial_controller',
    attribution_status = 'assessed',
    confidence = 'medium',
    link_basis = 'Title reports Houthi capture of Perim / Mayun Island; no event description is present.',
    metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'role_review_version','actor_role_v6_1','role_review_state','machine_assisted_proposed','role_review_basis','title_only'
    ),
    updated_at = now()
where event_actor_link_id = 'cb533fca-f3e0-4f06-b723-ed9f48ba14ea';

-- Ansar Allah — reported control/seizure of Mokha.
update public.pc_event_actor_links
set actor_role = 'territorial_controller',
    attribution_status = 'assessed',
    confidence = 'high',
    link_basis = 'Title states Houthis seized Mokha and description describes Houthi control and advance toward Hanish.',
    metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'role_review_version','actor_role_v6_1','role_review_state','machine_assisted_proposed','role_review_basis','title_description'
    ),
    updated_at = now()
where event_actor_link_id = '8fd6b21b-d019-4930-abb0-462078c28651';

-- IRGC — warning/threat against tanker crews.
update public.pc_event_actor_links
set actor_role = 'threat_actor',
    attribution_status = 'assessed',
    confidence = 'high',
    link_basis = 'Event reports an IRGC Navy warning to tanker crews with an explicit threat that ships could be targeted.',
    metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'role_review_version','actor_role_v6_1','role_review_state','machine_assisted_proposed','role_review_basis','title_description'
    ),
    updated_at = now()
where event_actor_link_id = 'f74a6be3-95be-49b4-9f60-647ea728b6da';

-- Ansar Allah — targeting-risk actor; title carries the actor linkage.
update public.pc_event_actor_links
set actor_role = 'threat_actor',
    attribution_status = 'assessed',
    confidence = 'medium',
    link_basis = 'Title links Houthi territorial advances and declared targeting criteria to increased risk for Saudi-linked vessels; description itself is impact-focused.',
    metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'role_review_version','actor_role_v6_1','role_review_state','machine_assisted_proposed','role_review_basis','title_description'
    ),
    updated_at = now()
where event_actor_link_id = 'd2ec5d44-5956-4aa5-96a1-881b4e4510e1';

-- Islamic Resistance in Iraq — subject/affected network in government disarmament effort.
update public.pc_event_actor_links
set actor_role = 'disarmament_subject',
    attribution_status = 'associated',
    confidence = 'medium',
    link_basis = 'Event concerns Baghdad militia disarmament; description identifies Islamic Resistance in Iraq as the umbrella containing hardline factions in scope.',
    metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'role_review_version','actor_role_v6_1','role_review_state','machine_assisted_proposed','role_review_basis','title_description'
    ),
    updated_at = now()
where event_actor_link_id = 'fc88f781-953b-4a50-a41b-6f9beea81879';

-- Ansar Allah — occupation/control.
update public.pc_event_actor_links
set actor_role = 'territorial_controller',
    attribution_status = 'assessed',
    confidence = 'high',
    link_basis = 'Description states Houthis overran government coastal pockets and occupied Al Mokha city/port and Perim Island.',
    metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'role_review_version','actor_role_v6_1','role_review_state','machine_assisted_proposed','role_review_basis','title_description'
    ),
    updated_at = now()
where event_actor_link_id = '148c0b9e-ade3-44e3-be73-aacbad9f4520';

-- Ansar Allah — refinery attack.
update public.pc_event_actor_links
set actor_role = 'initiator',
    attribution_status = 'assessed',
    confidence = 'high',
    link_basis = 'Title and description state Houthi forces attacked and struck the Jazan refining complex.',
    metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'role_review_version','actor_role_v6_1','role_review_state','machine_assisted_proposed','role_review_basis','title_description'
    ),
    updated_at = now()
where event_actor_link_id = '6f7c0208-1e25-4630-825d-6aa003dc1b92';

-- IRGC — precipitating attempted attacks, but CENTCOM is initiator of the event itself.
update public.pc_event_actor_links
set actor_role = 'contextual_actor',
    attribution_status = 'context_only',
    confidence = 'high',
    link_basis = 'Event itself is a CENTCOM strike; IRGC is referenced as the actor behind attempted missile attacks that preceded the strike, so it is contextual rather than the initiator of this event.',
    metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'role_review_version','actor_role_v6_1','role_review_state','machine_assisted_proposed','role_review_basis','title_description'
    ),
    updated_at = now()
where event_actor_link_id = 'b3425fb6-617d-4d46-8c3a-252ba414cb7a';

-- Ansar Allah — target of government attack.
update public.pc_event_actor_links
set actor_role = 'target',
    attribution_status = 'assessed',
    confidence = 'high',
    link_basis = 'Description explicitly states a government attack on Houthi positions.',
    metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'role_review_version','actor_role_v6_1','role_review_state','machine_assisted_proposed','role_review_basis','description'
    ),
    updated_at = now()
where event_actor_link_id = '6aa7905b-df75-4f64-9a10-b11635c4aa33';

-- PKK — subject of disarmament implementation.
update public.pc_event_actor_links
set actor_role = 'disarmament_subject',
    attribution_status = 'assessed',
    confidence = 'high',
    link_basis = 'Title and description describe a Turkey-Iraq-KRG mechanism covering PKK camps, weapons and near-border positions.',
    metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'role_review_version','actor_role_v6_1','role_review_state','machine_assisted_proposed','role_review_basis','title_description'
    ),
    updated_at = now()
where event_actor_link_id = '081440bf-9ece-4c89-bba9-78ee01ab37d5';

-- Ansar Allah — advancing actor; best represented as threat actor in this event.
update public.pc_event_actor_links
set actor_role = 'threat_actor',
    attribution_status = 'assessed',
    confidence = 'medium',
    link_basis = 'Description states reinforcements were deployed to halt a Houthi advance; the Houthi role is the advancing threat rather than the reinforcement initiator.',
    metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'role_review_version','actor_role_v6_1','role_review_state','machine_assisted_proposed','role_review_basis','description'
    ),
    updated_at = now()
where event_actor_link_id = '180ec041-615c-4645-a37b-234b772e98c6';

-- Ansar Allah — offensive campaign initiator.
update public.pc_event_actor_links
set actor_role = 'initiator',
    attribution_status = 'assessed',
    confidence = 'high',
    link_basis = 'Description states the Houthis launched a month-long missile, drone, artillery and ground offensive.',
    metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'role_review_version','actor_role_v6_1','role_review_state','machine_assisted_proposed','role_review_basis','title_description'
    ),
    updated_at = now()
where event_actor_link_id = 'c6af2189-bfea-43ad-b239-fd45ba72535a';

-- Ansar Allah — threat caused rerouting.
update public.pc_event_actor_links
set actor_role = 'threat_actor',
    attribution_status = 'assessed',
    confidence = 'high',
    link_basis = 'Description states vessels altered course after Houthi threats against Saudi-linked traffic.',
    metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'role_review_version','actor_role_v6_1','role_review_state','machine_assisted_proposed','role_review_basis','title_description'
    ),
    updated_at = now()
where event_actor_link_id = '99bef6cd-032a-458d-a497-0abe747ceb03';

-- Ansar Allah — claimed targeting LAYLA; do not infer responsibility for ENCELIA.
update public.pc_event_actor_links
set actor_role = 'claimant',
    attribution_status = 'claimed',
    confidence = 'high',
    link_basis = 'Description says Houthis claimed targeting tanker LAYLA; it does not attribute the strike on ENCELIA to them.',
    metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'role_review_version','actor_role_v6_1','role_review_state','machine_assisted_proposed','role_review_basis','description',
        'attribution_caution','Do not infer Houthi responsibility for ENCELIA from the supplied event text.'
    ),
    updated_at = now()
where event_actor_link_id = '67fc7089-e0e0-4bb2-b1cd-2eb27047cfe5';

-- Ansar Allah — blockade/threat actor.
update public.pc_event_actor_links
set actor_role = 'threat_actor',
    attribution_status = 'assessed',
    confidence = 'high',
    link_basis = 'Title and description state a Houthi maritime ban/blockade on Saudi port traffic with threats against non-compliant vessels.',
    metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'role_review_version','actor_role_v6_1','role_review_state','machine_assisted_proposed','role_review_basis','title_description'
    ),
    updated_at = now()
where event_actor_link_id = '5d3ce778-3108-436f-87bb-9619ee7f82a1';

-- Ansar Allah — explicit declared targeting warning.
update public.pc_event_actor_links
set actor_role = 'threat_actor',
    attribution_status = 'assessed',
    confidence = 'high',
    link_basis = 'Description states the Houthis declared a naval blockade and warned shipping companies they risked attack if calling Saudi ports.',
    metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'role_review_version','actor_role_v6_1','role_review_state','machine_assisted_proposed','role_review_basis','title_description'
    ),
    updated_at = now()
where event_actor_link_id = 'a4bf7a0f-709c-4f08-8c32-eca7c09c27cb';

-- PKK — negotiating party.
update public.pc_event_actor_links
set actor_role = 'negotiating_party',
    attribution_status = 'assessed',
    confidence = 'high',
    link_basis = 'Event concerns Turkey-PKK peace-process negotiations and explicitly describes PKK demands for legal guarantees.',
    metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'role_review_version','actor_role_v6_1','role_review_state','machine_assisted_proposed','role_review_basis','title_description'
    ),
    updated_at = now()
where event_actor_link_id = 'cd42bdc3-aa06-4126-a94a-5d2dfa7bd261';

-- IRGC — directing actor for covert cells; title carries attribution.
update public.pc_event_actor_links
set actor_role = 'directing_actor',
    attribution_status = 'assessed',
    confidence = 'medium',
    link_basis = 'Title characterises the Iraqi covert cells as IRGC-directed; description details the campaign but does not independently repeat the directing relationship.',
    metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'role_review_version','actor_role_v6_1','role_review_state','machine_assisted_proposed','role_review_basis','title_description'
    ),
    updated_at = now()
where event_actor_link_id = 'ffff9c55-afc3-47a6-89f1-60bfeee7dbcd';

-- IRGC — directing actor, explicitly supported in description.
update public.pc_event_actor_links
set actor_role = 'directing_actor',
    attribution_status = 'assessed',
    confidence = 'high',
    link_basis = 'Description states the covert cells operated outside established militia structures and reported directly to the IRGC.',
    metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'role_review_version','actor_role_v6_1','role_review_state','machine_assisted_proposed','role_review_basis','title_description'
    ),
    updated_at = now()
where event_actor_link_id = 'e8c8c425-0615-43c6-9850-f1123d510a69';

-- Ansar Allah — title-only reported seizure of Hanish islands.
update public.pc_event_actor_links
set actor_role = 'territorial_controller',
    attribution_status = 'assessed',
    confidence = 'medium',
    link_basis = 'Title reports Houthi forces seized Greater and Lesser Hanish islands; no description is present.',
    metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
        'role_review_version','actor_role_v6_1','role_review_state','machine_assisted_proposed','role_review_basis','title_only'
    ),
    updated_at = now()
where event_actor_link_id = '54342172-c9e7-413b-b66e-c58ef13ae220';

commit;

-- ============================================================================
-- REVIEW AFTER RUN
-- ============================================================================

-- 1. Role distribution:
-- select actor_role, attribution_status, confidence, count(*) as links
-- from public.pc_event_actor_links
-- where metadata->>'role_review_version' = 'actor_role_v6_1'
-- group by actor_role, attribution_status, confidence
-- order by links desc, actor_role;

-- 2. Inspect all proposed classifications:
-- select
--     l.event_actor_link_id,
--     l.event_id,
--     a.canonical_name,
--     l.actor_role,
--     l.attribution_status,
--     l.confidence,
--     l.link_basis,
--     l.analyst_reviewed,
--     e.title
-- from public.pc_event_actor_links l
-- join public.pc_actors a on a.actor_id = l.actor_id
-- left join public.pc_events e on e.event_id = l.event_id
-- where l.metadata->>'role_review_version' = 'actor_role_v6_1'
-- order by e.start_date desc nulls last, a.canonical_name;

-- 3. After YOU approve the classifications, mark them analyst-reviewed:
-- update public.pc_event_actor_links
-- set analyst_reviewed = true,
--     metadata = coalesce(metadata,'{}'::jsonb) || jsonb_build_object(
--         'role_review_state','analyst_approved',
--         'analyst_reviewed_at', now()
--     ),
--     updated_at = now()
-- where metadata->>'role_review_version' = 'actor_role_v6_1';

-- 4. Actor directory after approval / role refinement:
-- select *
-- from public.v_pc_actor_directory
-- order by linked_events desc, canonical_name;
