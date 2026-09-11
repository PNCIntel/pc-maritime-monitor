-- Initial deterministic event routing. AI/admin review can refine scores later.
-- The principle: Intelligence is event-led. Ports/companies are context, not inclusion criteria.

update pc_events set
  event_nature = case
    when lower(coalesce(event_family,'')||' '||coalesce(event_type,'')||' '||coalesce(title,'')) ~
      '(war|conflict|attack|strike / fire|missile|drone|piracy|hijack|boarding|seizure|smuggl|traffick|fraud|crime|terror|sabotage|mine|sanction|interdict)'
      then 'SECURITY'
    when lower(coalesce(event_family,'')||' '||coalesce(event_type,'')||' '||coalesce(title,'')||' '||coalesce(description,'')) ~
      '(weather|typhoon|hurricane|cyclone|flood|earthquake|wildfire|storm|grounding|collision|allision|capsize|sinking|fire|explosion|labour|strike|protest|closure|outage|disruption|low water|cyber)'
      then 'DISRUPTION'
    when lower(coalesce(event_family,'')||' '||coalesce(event_type,'')||' '||coalesce(title,'')) ~
      '(investment|acquisition|terminal opening|commissioning|new crane|equipment order|vessel order|contract award|earnings|financing|service launch)'
      then 'CORPORATE'
    else coalesce(event_nature,'OTHER') end;

update pc_events set
  intelligence_relevance = case
    when event_nature='SECURITY' then greatest(intelligence_relevance,4)
    when event_nature='DISRUPTION' then greatest(intelligence_relevance,3)
    when event_nature='CORPORATE' then 0
    else intelligence_relevance end,
  intelligence_visible = case
    when event_nature in ('SECURITY','DISRUPTION') then true
    when event_nature='CORPORATE' then false
    else intelligence_visible end,
  trade_relevance = case
    when event_nature in ('SECURITY','DISRUPTION') and nullif(commercial_impact,'') is not null then greatest(trade_relevance,3)
    when event_nature='CORPORATE' then greatest(trade_relevance,2)
    else trade_relevance end,
  trade_visible = case
    when event_nature in ('SECURITY','DISRUPTION','CORPORATE') then true
    else trade_visible end,
  alert_worthy = case
    when event_nature in ('SECURITY','DISRUPTION') and lower(coalesce(severity,'')) in ('critical','high','severe') then true
    else alert_worthy end;
