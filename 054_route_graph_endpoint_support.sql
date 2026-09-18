-- Power & Corridors
-- 054_route_graph_endpoint_support.sql
-- Purpose: make route/transport-route endpoints first-class graph objects for
-- pc_relationships, pc_event_links and deferred canonical processing.
-- Safe to run repeatedly.

begin;

create or replace function public.pc_object_exists(p_object_type text,p_id text)
returns boolean
language plpgsql
stable
security definer
set search_path=public
as $$
declare v boolean:=false;
declare t text:=lower(coalesce(p_object_type,''));
begin
    if t in ('company','organisation','organization') then t:='entity'; end if;
    if t in ('vessel','ship','aircraft') then t:='mobile_asset'; end if;
    if t in ('transport_route','corridor','network') then t:='route'; end if;
    if t='deal' then t:='transaction'; end if;

    case t
      when 'entity' then
        select exists(select 1 from pc_entities where entity_id::text=p_id) into v;
      when 'asset' then
        select exists(select 1 from pc_assets where asset_id::text=p_id) into v;
      when 'mobile_asset' then
        select exists(select 1 from pc_mobile_assets where mobile_asset_id::text=p_id) into v;
      when 'event' then
        select exists(select 1 from pc_events where event_id::text=p_id) into v;
      when 'route' then
        select exists(select 1 from pc_transport_routes where route_id::text=p_id) into v;
      when 'transaction' then
        select exists(select 1 from pc_transactions where transaction_id::text=p_id) into v;
      else
        raise exception 'Unsupported object type: %',p_object_type;
    end case;
    return v;
end;
$$;

create or replace function public.pc_object_name(p_object_type text,p_id text)
returns text
language plpgsql
stable
security definer
set search_path=public
as $$
declare v text;
declare t text:=lower(coalesce(p_object_type,''));
begin
    if t in ('company','organisation','organization') then t:='entity'; end if;
    if t in ('vessel','ship','aircraft') then t:='mobile_asset'; end if;
    if t in ('transport_route','corridor','network') then t:='route'; end if;
    if t='deal' then t:='transaction'; end if;

    case t
      when 'entity' then
        select name into v from pc_entities where entity_id::text=p_id;
      when 'asset' then
        select name into v from pc_assets where asset_id::text=p_id;
      when 'mobile_asset' then
        select name into v from pc_mobile_assets where mobile_asset_id::text=p_id;
      when 'event' then
        select title into v from pc_events where event_id::text=p_id;
      when 'route' then
        select route_name into v from pc_transport_routes where route_id::text=p_id;
      when 'transaction' then
        select coalesce(title,transaction_id::text) into v
          from pc_transactions where transaction_id::text=p_id;
      else
        raise exception 'Unsupported object type: %',p_object_type;
    end case;
    return v;
end;
$$;

-- Optional smoke test: confirms route endpoints are accepted by the generic helpers.
do $$
declare rid text;
begin
    select route_id::text into rid from pc_transport_routes limit 1;
    if rid is not null then
        perform public.pc_object_exists('route',rid);
        perform public.pc_object_name('route',rid);
    end if;
end;
$$;

commit;
