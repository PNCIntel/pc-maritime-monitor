-- Power & Corridors
-- 046_mobile_asset_identity_flexibility.sql
--
-- Purpose:
-- Allow newbuild/workboat/mobile-asset records to enter the canonical resolver
-- when IMO/MMSI/flag are not yet available, provided there is still a defensible
-- identity package: name + subtype/type + source evidence.
--
-- This is important for newbuild hulls, government craft, workboats, ferries,
-- tug deliveries and vessels reported before IMO/MMSI publication.
--
-- Existing strong-ID behavior remains preferred by pc_resolve_upsert_mobile_asset:
-- mobile_asset_id -> IMO -> MMSI -> alias -> normalized name/type/flag -> create.

begin;

create or replace function public.pc_minimum_identity_ok(
    p_object_type text,
    p_payload jsonb
)
returns boolean
language plpgsql
immutable
as $$
declare
    t text:=lower(p_object_type);
    v_has_source boolean :=
        nullif(trim(coalesce(p_payload->>'source_url','')),'') is not null
        or (
            jsonb_typeof(p_payload->'research_sources')='array'
            and jsonb_array_length(p_payload->'research_sources') > 0
        )
        or (
            jsonb_typeof(p_payload->'metadata')='object'
            and jsonb_typeof((p_payload->'metadata')->'research_sources')='array'
            and jsonb_array_length((p_payload->'metadata')->'research_sources') > 0
        );
begin
    if t='entity' then
        return nullif(trim(p_payload->>'name'),'') is not null
           and (
                nullif(trim(p_payload->>'country'),'') is not null
                or nullif(trim(p_payload->>'hq_country'),'') is not null
                or nullif(trim(p_payload->>'entity_type'),'') is not null
                or v_has_source
           );

    elsif t='asset' then
        return nullif(trim(p_payload->>'name'),'') is not null
           and nullif(trim(coalesce(p_payload->>'asset_type',p_payload->>'type')),'') is not null
           and (
                nullif(trim(p_payload->>'country'),'') is not null
                or nullif(trim(p_payload->>'region_city'),'') is not null
                or nullif(trim(p_payload->>'latitude_longitude'),'') is not null
                or v_has_source
           );

    elsif t in ('mobile_asset','vessel') then
        return nullif(trim(p_payload->>'name'),'') is not null
           and (
                -- strongest identifiers
                nullif(trim(p_payload->>'imo'),'') is not null
                or nullif(trim(p_payload->>'mmsi'),'') is not null
                or nullif(trim(p_payload->>'call_sign_or_registration'),'') is not null
                -- contextual identity
                or (
                    nullif(trim(p_payload->>'flag'),'') is not null
                    and nullif(trim(coalesce(p_payload->>'subtype',p_payload->>'asset_type')),'') is not null
                )
                -- source-backed newbuild/workboat identity
                or (
                    nullif(trim(coalesce(p_payload->>'subtype',p_payload->>'asset_type')),'') is not null
                    and v_has_source
                )
           );

    elsif t='event' then
        return coalesce(
                nullif(trim(p_payload->>'title'),''),
                nullif(trim(p_payload->>'name'),'')
               ) is not null
           and (
                nullif(trim(p_payload->>'start_date'),'') is not null
                or nullif(trim(p_payload->>'event_date'),'') is not null
                or v_has_source
           );
    end if;

    return false;
end;
$$;

commit;

-- Optional smoke tests:
-- select public.pc_minimum_identity_ok(
--   'mobile_asset',
--   '{"name":"HULL 096","asset_type":"vessel","subtype":"battery_electric_ferry","source_url":"https://example.com"}'::jsonb
-- );
--
-- Expected: true
