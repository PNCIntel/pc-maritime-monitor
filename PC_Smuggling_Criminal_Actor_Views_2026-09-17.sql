-- Criminal-first actor views for P&C Intelligence
-- Generated 2026-09-17

create or replace view public.v_pc_illicit_actor_directory as
select *
from public.v_pc_actor_directory
where coalesce(metadata->>'actor_layer','') = 'illicit'
   or actor_class in ('organized_crime_group','armed_group')
   or (
       actor_class='person'
       and actor_subtype in ('convicted_migrant_smuggler','alleged_drug_trafficker')
   );

create or replace view public.v_pc_illicit_event_actor_links as
select l.*
from public.pc_event_actor_links l
join public.pc_actors a on a.actor_id=l.actor_id
where coalesce(a.metadata->>'actor_layer','') = 'illicit'
   or a.actor_class in ('organized_crime_group','armed_group')
   or (
       a.actor_class='person'
       and a.actor_subtype in ('convicted_migrant_smuggler','alleged_drug_trafficker')
   );

create or replace view public.v_pc_enforcement_event_actor_links as
select l.*
from public.pc_event_actor_links l
join public.pc_actors a on a.actor_id=l.actor_id
where coalesce(a.metadata->>'actor_layer','') = 'enforcement'
   or a.actor_class in ('law_enforcement_agency','state_security_actor');

-- Recommended app behavior:
-- Default "Actors / Networks" analytics should query v_pc_illicit_event_actor_links.
-- Add an optional layer selector: Criminal / Enforcement / All.
