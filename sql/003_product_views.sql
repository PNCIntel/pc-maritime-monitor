-- Product-specific routing views. Corporate developments stay out of Intelligence unless
-- they are separately classified as a security/operational event.

create or replace view pc_vw_trade_alerts with (security_invoker=true) as
select e.*
from pc_events e
where e.trade_visible
  and e.trade_relevance >= 2
  and (
    e.event_nature in ('DISRUPTION','SECURITY')
    or coalesce(e.alert_worthy,false)
  )
order by e.start_date desc nulls last;

create or replace view pc_vw_intelligence_events with (security_invoker=true) as
select e.*
from pc_events e
where e.intelligence_visible
  and e.intelligence_relevance >= 2
  and coalesce(e.event_nature,'OTHER') <> 'CORPORATE'
order by e.start_date desc nulls last;

create or replace view pc_vw_intelligence_operating_picture with (security_invoker=true) as
select e.*
from pc_events e
where e.intelligence_visible
  and e.intelligence_relevance >= 3
  and coalesce(e.event_nature,'OTHER') <> 'CORPORATE'
order by e.intelligence_relevance desc, e.start_date desc nulls last;

create or replace view pc_vw_trade_company_network with (security_invoker=true) as
select e.entity_id,e.name,e.entity_type,e.subtype,e.hq_country,r.relationship_id,
       r.relationship_type,r.target_type,r.target_id,r.ownership_percent,r.operating_control,
       r.valid_from,r.valid_to,r.confidence
from pc_entities e
left join pc_relationships r on r.source_type='entity' and r.source_id=e.entity_id;

create or replace view pc_vw_event_exposure with (security_invoker=true) as
select ev.event_id,ev.start_date,ev.event_nature,ev.event_family,ev.event_type,ev.severity,
       ev.title,ev.trade_relevance,ev.intelligence_relevance,
       el.linked_type,el.linked_id,el.linked_name,el.relationship,
       ev.operational_impact,ev.commercial_impact
from pc_events ev
join pc_event_links el on el.event_id=ev.event_id;
