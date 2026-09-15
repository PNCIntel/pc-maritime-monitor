-- Power & Corridors
-- 043_canonical_identity_naming_audit.sql
-- Purpose:
--   1) establish canonical naming/alias infrastructure
--   2) normalize vessel display names to UPPERCASE
--   3) expose duplicate-candidate views for entities, assets and mobile assets
--   4) do NOT automatically merge or delete canonical records
--
-- Naming conventions:
--   vessels/mobile maritime assets -> UPPERCASE display name
--   ports/terminals/fixed assets   -> official display name (no forced title-case)
--   companies/entities            -> official corporate styling (no forced title-case)
--   aliases                       -> source spelling, typo, former name, abbreviation
--
-- Safe to run repeatedly.
-- v2 is schema-tolerant: current pc_entities uses hq_country rather than country.

begin;

create extension if not exists pg_trgm;

create or replace function public.pc_norm_identity_text(p_text text)
returns text
language sql
immutable
as $$
    select nullif(
        regexp_replace(
            lower(trim(coalesce(p_text,''))),
            '[^a-z0-9]+',
            ' ',
            'g'
        ),
        ''
    );
$$;

create or replace function public.pc_norm_compact_text(p_text text)
returns text
language sql
immutable
as $$
    select nullif(
        regexp_replace(lower(trim(coalesce(p_text,''))), '[^a-z0-9]+', '', 'g'),
        ''
    );
$$;

-- Alias registry. One canonical object may have many names/spellings.
create table if not exists public.pc_identity_aliases_v2 (
    alias_id bigserial primary key,
    object_type text not null check (object_type in ('entity','asset','mobile_asset','event')),
    canonical_id text not null,
    alias_name text not null,
    normalized_alias text generated always as (public.pc_norm_identity_text(alias_name)) stored,
    alias_type text not null default 'alternate', -- official, alternate, former, abbreviation, typo, source
    source_url text,
    source_id text,
    confidence numeric,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (object_type, canonical_id, normalized_alias)
);

create index if not exists idx_pc_identity_aliases_v2_lookup
    on public.pc_identity_aliases_v2(object_type, normalized_alias);

create index if not exists idx_pc_identity_aliases_v2_trgm
    on public.pc_identity_aliases_v2 using gin (normalized_alias gin_trgm_ops);

-- Central naming policy helper. Only vessel/mobile maritime names are transformed automatically.
create or replace function public.pc_apply_display_name_policy(
    p_object_type text,
    p_name text,
    p_asset_type text default null,
    p_subtype text default null
)
returns text
language plpgsql
immutable
as $$
declare
    v_kind text := lower(coalesce(p_object_type,''));
    v_type text := lower(coalesce(p_asset_type,'') || ' ' || coalesce(p_subtype,''));
    v_name text := nullif(trim(p_name),'');
begin
    if v_name is null then
        return null;
    end if;

    if v_kind='mobile_asset'
       and (
           v_type ~ '(vessel|ship|tanker|bulk|container|ferry|cruise|ro[- ]?ro|offshore|osv|tug|barge|fishing|lng|lpg|carrier|dredger|yacht|naval|boat)'
           or v_type=''
       )
    then
        return upper(v_name);
    end if;

    -- Preserve official style for entities and fixed assets.
    return v_name;
end;
$$;

-- Preserve old spelling as alias before changing vessel display names.
insert into public.pc_identity_aliases_v2(object_type,canonical_id,alias_name,alias_type,metadata)
select
    'mobile_asset',
    m.mobile_asset_id::text,
    m.name,
    'source',
    jsonb_build_object('reason','pre_043_display_name_normalization')
from public.pc_mobile_assets m
where nullif(trim(m.name),'') is not null
  and m.name <> public.pc_apply_display_name_policy(
      'mobile_asset',
      m.name,
      coalesce(to_jsonb(m)->>'asset_type', to_jsonb(m)->>'mobile_asset_type', to_jsonb(m)->>'vessel_type'),
      coalesce(to_jsonb(m)->>'subtype','')
  )
on conflict (object_type,canonical_id,normalized_alias) do nothing;

-- Normalize vessel/mobile maritime display names.
update public.pc_mobile_assets m
set name = public.pc_apply_display_name_policy(
    'mobile_asset',
    m.name,
    coalesce(to_jsonb(m)->>'asset_type', to_jsonb(m)->>'mobile_asset_type', to_jsonb(m)->>'vessel_type'),
    coalesce(to_jsonb(m)->>'subtype','')
)
where nullif(trim(m.name),'') is not null
  and m.name <> public.pc_apply_display_name_policy(
      'mobile_asset',
      m.name,
      coalesce(to_jsonb(m)->>'asset_type', to_jsonb(m)->>'mobile_asset_type', to_jsonb(m)->>'vessel_type'),
      coalesce(to_jsonb(m)->>'subtype','')
  );

-- Seed canonical display names as official aliases.
insert into public.pc_identity_aliases_v2(object_type,canonical_id,alias_name,alias_type)
select 'entity', entity_id::text, name, 'official'
from public.pc_entities
where nullif(trim(name),'') is not null
on conflict (object_type,canonical_id,normalized_alias) do nothing;

insert into public.pc_identity_aliases_v2(object_type,canonical_id,alias_name,alias_type)
select 'asset', asset_id::text, name, 'official'
from public.pc_assets
where nullif(trim(name),'') is not null
on conflict (object_type,canonical_id,normalized_alias) do nothing;

insert into public.pc_identity_aliases_v2(object_type,canonical_id,alias_name,alias_type)
select 'mobile_asset', mobile_asset_id::text, name, 'official'
from public.pc_mobile_assets
where nullif(trim(name),'') is not null
on conflict (object_type,canonical_id,normalized_alias) do nothing;

-- Strong-identifier audits.
-- Use to_jsonb(row) so this remains compatible with schema variants.
create or replace view public.pc_v_duplicate_mobile_asset_identifiers as
select
    'IMO'::text as identifier_type,
    regexp_replace(coalesce(to_jsonb(m)->>'imo',''),'[^0-9]','','g') as identifier_value,
    count(*) as record_count,
    array_agg(m.mobile_asset_id::text order by m.mobile_asset_id::text) as canonical_ids,
    array_agg(m.name order by m.mobile_asset_id::text) as names
from public.pc_mobile_assets m
where nullif(regexp_replace(coalesce(to_jsonb(m)->>'imo',''),'[^0-9]','','g'),'') is not null
group by regexp_replace(coalesce(to_jsonb(m)->>'imo',''),'[^0-9]','','g')
having count(*) > 1
union all
select
    'MMSI'::text,
    regexp_replace(coalesce(to_jsonb(m)->>'mmsi',''),'[^0-9]','','g'),
    count(*),
    array_agg(m.mobile_asset_id::text order by m.mobile_asset_id::text),
    array_agg(m.name order by m.mobile_asset_id::text)
from public.pc_mobile_assets m
where nullif(regexp_replace(coalesce(to_jsonb(m)->>'mmsi',''),'[^0-9]','','g'),'') is not null
group by regexp_replace(coalesce(to_jsonb(m)->>'mmsi',''),'[^0-9]','','g')
having count(*) > 1;

-- Exact normalized-name duplicate candidates.
-- pc_entities uses hq_country in the current P&C schema. The COALESCE also supports
-- older/newer variants that may expose country instead.
create or replace view public.pc_v_duplicate_entity_candidates as
select
    public.pc_norm_identity_text(e.name) as normalized_name,
    public.pc_norm_identity_text(
        coalesce(to_jsonb(e)->>'hq_country', to_jsonb(e)->>'country')
    ) as normalized_country,
    count(*) as record_count,
    array_agg(e.entity_id::text order by e.entity_id::text) as canonical_ids,
    array_agg(e.name order by e.entity_id::text) as names,
    array_agg(
        coalesce(to_jsonb(e)->>'entity_type','')
        order by e.entity_id::text
    ) as entity_types
from public.pc_entities e
where public.pc_norm_identity_text(e.name) is not null
group by
    public.pc_norm_identity_text(e.name),
    public.pc_norm_identity_text(
        coalesce(to_jsonb(e)->>'hq_country', to_jsonb(e)->>'country')
    )
having count(*) > 1;

create or replace view public.pc_v_duplicate_asset_candidates as
select
    public.pc_norm_identity_text(a.name) as normalized_name,
    public.pc_norm_identity_text(
        coalesce(to_jsonb(a)->>'country', to_jsonb(a)->>'hq_country')
    ) as normalized_country,
    public.pc_norm_identity_text(
        coalesce(to_jsonb(a)->>'asset_type', to_jsonb(a)->>'type')
    ) as normalized_asset_type,
    count(*) as record_count,
    array_agg(a.asset_id::text order by a.asset_id::text) as canonical_ids,
    array_agg(a.name order by a.asset_id::text) as names,
    array_agg(
        coalesce(to_jsonb(a)->>'region_city', to_jsonb(a)->>'city', to_jsonb(a)->>'location')
        order by a.asset_id::text
    ) as locations
from public.pc_assets a
where public.pc_norm_identity_text(a.name) is not null
group by
    public.pc_norm_identity_text(a.name),
    public.pc_norm_identity_text(
        coalesce(to_jsonb(a)->>'country', to_jsonb(a)->>'hq_country')
    ),
    public.pc_norm_identity_text(
        coalesce(to_jsonb(a)->>'asset_type', to_jsonb(a)->>'type')
    )
having count(*) > 1;

create or replace view public.pc_v_duplicate_mobile_asset_candidates as
select
    public.pc_norm_identity_text(m.name) as normalized_name,
    public.pc_norm_identity_text(
        coalesce(to_jsonb(m)->>'flag', to_jsonb(m)->>'flag_state')
    ) as normalized_flag,
    public.pc_norm_identity_text(
        coalesce(
            to_jsonb(m)->>'asset_type',
            to_jsonb(m)->>'mobile_asset_type',
            to_jsonb(m)->>'vessel_type',
            to_jsonb(m)->>'type'
        )
    ) as normalized_asset_type,
    count(*) as record_count,
    array_agg(m.mobile_asset_id::text order by m.mobile_asset_id::text) as canonical_ids,
    array_agg(m.name order by m.mobile_asset_id::text) as names,
    array_agg(to_jsonb(m)->>'imo' order by m.mobile_asset_id::text) as imos,
    array_agg(to_jsonb(m)->>'mmsi' order by m.mobile_asset_id::text) as mmsis
from public.pc_mobile_assets m
where public.pc_norm_identity_text(m.name) is not null
group by
    public.pc_norm_identity_text(m.name),
    public.pc_norm_identity_text(
        coalesce(to_jsonb(m)->>'flag', to_jsonb(m)->>'flag_state')
    ),
    public.pc_norm_identity_text(
        coalesce(
            to_jsonb(m)->>'asset_type',
            to_jsonb(m)->>'mobile_asset_type',
            to_jsonb(m)->>'vessel_type',
            to_jsonb(m)->>'type'
        )
    )
having count(*) > 1;

-- Fuzzy spelling candidates for fixed assets such as Zayed/Zayad Port.
-- AUDIT ONLY. Similarity alone is never sufficient to merge automatically.
create or replace view public.pc_v_fuzzy_asset_name_candidates as
select
    a.asset_id::text as asset_id_a,
    a.name as name_a,
    b.asset_id::text as asset_id_b,
    b.name as name_b,
    coalesce(to_jsonb(a)->>'asset_type', to_jsonb(a)->>'type') as asset_type,
    coalesce(to_jsonb(a)->>'country', to_jsonb(a)->>'hq_country') as country,
    coalesce(to_jsonb(a)->>'region_city', to_jsonb(a)->>'city', to_jsonb(a)->>'location') as region_city,
    similarity(public.pc_norm_identity_text(a.name), public.pc_norm_identity_text(b.name)) as name_similarity
from public.pc_assets a
join public.pc_assets b
  on a.asset_id::text < b.asset_id::text
 and (
      nullif(coalesce(to_jsonb(a)->>'country', to_jsonb(a)->>'hq_country'),'') is null
      or nullif(coalesce(to_jsonb(b)->>'country', to_jsonb(b)->>'hq_country'),'') is null
      or public.pc_norm_identity_text(
            coalesce(to_jsonb(a)->>'country', to_jsonb(a)->>'hq_country')
         ) = public.pc_norm_identity_text(
            coalesce(to_jsonb(b)->>'country', to_jsonb(b)->>'hq_country')
         )
 )
 and (
      nullif(coalesce(to_jsonb(a)->>'asset_type', to_jsonb(a)->>'type'),'') is null
      or nullif(coalesce(to_jsonb(b)->>'asset_type', to_jsonb(b)->>'type'),'') is null
      or public.pc_norm_identity_text(
            coalesce(to_jsonb(a)->>'asset_type', to_jsonb(a)->>'type')
         ) = public.pc_norm_identity_text(
            coalesce(to_jsonb(b)->>'asset_type', to_jsonb(b)->>'type')
         )
 )
where similarity(
        public.pc_norm_identity_text(a.name),
        public.pc_norm_identity_text(b.name)
      ) >= 0.72;

-- One summary view for pre-reload review.
create or replace view public.pc_v_identity_hygiene_summary as
select 'duplicate_entity_groups'::text as check_name, count(*)::bigint as issue_count
from public.pc_v_duplicate_entity_candidates
union all
select 'duplicate_asset_groups', count(*) from public.pc_v_duplicate_asset_candidates
union all
select 'duplicate_mobile_asset_groups', count(*) from public.pc_v_duplicate_mobile_asset_candidates
union all
select 'duplicate_imo_mmsi_groups', count(*) from public.pc_v_duplicate_mobile_asset_identifiers
union all
select 'fuzzy_asset_pairs', count(*) from public.pc_v_fuzzy_asset_name_candidates;

grant select on public.pc_v_duplicate_mobile_asset_identifiers to authenticated;
grant select on public.pc_v_duplicate_entity_candidates to authenticated;
grant select on public.pc_v_duplicate_asset_candidates to authenticated;
grant select on public.pc_v_duplicate_mobile_asset_candidates to authenticated;
grant select on public.pc_v_fuzzy_asset_name_candidates to authenticated;
grant select on public.pc_v_identity_hygiene_summary to authenticated;

commit;

-- Suggested review queries:
-- select * from public.pc_v_identity_hygiene_summary;
-- select * from public.pc_v_duplicate_asset_candidates;
-- select * from public.pc_v_fuzzy_asset_name_candidates
--   where lower(name_a) like '%zay%' or lower(name_b) like '%zay%';
-- select * from public.pc_v_duplicate_mobile_asset_identifiers;
