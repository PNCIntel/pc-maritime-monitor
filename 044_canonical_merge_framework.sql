-- Power & Corridors
-- 044_canonical_merge_framework.sql
-- Purpose: safely merge a confirmed duplicate canonical object into a survivor.
-- Rewrites graph edges first, stores the duplicate name as an alias, and records an audit.
-- This migration does NOT automatically choose duplicates to merge.
--
-- Run 043 first.

begin;

create table if not exists public.pc_canonical_merge_audit (
    merge_audit_id bigserial primary key,
    merged_at timestamptz not null default now(),
    object_type text not null,
    survivor_id text not null,
    duplicate_id text not null,
    survivor_name text,
    duplicate_name text,
    rewritten_relationships integer not null default 0,
    rewritten_event_links integer not null default 0,
    rewritten_direct_refs integer not null default 0,
    duplicate_deleted boolean not null default false,
    notes text,
    metadata jsonb not null default '{}'::jsonb
);

create or replace function public.pc_object_exists(p_object_type text,p_id text)
returns boolean
language plpgsql
stable
security definer
set search_path=public
as $$
declare v boolean:=false;
begin
    case lower(p_object_type)
      when 'entity' then select exists(select 1 from pc_entities where entity_id::text=p_id) into v;
      when 'asset' then select exists(select 1 from pc_assets where asset_id::text=p_id) into v;
      when 'mobile_asset' then select exists(select 1 from pc_mobile_assets where mobile_asset_id::text=p_id) into v;
      when 'vessel' then select exists(select 1 from pc_mobile_assets where mobile_asset_id::text=p_id) into v;
      when 'event' then select exists(select 1 from pc_events where event_id::text=p_id) into v;
      else raise exception 'Unsupported object type: %',p_object_type;
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
begin
    case lower(p_object_type)
      when 'entity' then select name into v from pc_entities where entity_id::text=p_id;
      when 'asset' then select name into v from pc_assets where asset_id::text=p_id;
      when 'mobile_asset' then select name into v from pc_mobile_assets where mobile_asset_id::text=p_id;
      when 'vessel' then select name into v from pc_mobile_assets where mobile_asset_id::text=p_id;
      when 'event' then select title into v from pc_events where event_id::text=p_id;
      else raise exception 'Unsupported object type: %',p_object_type;
    end case;
    return v;
end;
$$;

-- Generic helper: if a direct-reference column exists on a table, update it.
create or replace function public.pc_rewrite_direct_reference(
    p_table text,
    p_column text,
    p_old_id text,
    p_new_id text
)
returns integer
language plpgsql
security definer
set search_path=public
as $$
declare
    v_count integer:=0;
begin
    if to_regclass('public.'||p_table) is null then
        return 0;
    end if;

    if not exists (
        select 1
        from information_schema.columns
        where table_schema='public'
          and table_name=p_table
          and column_name=p_column
    ) then
        return 0;
    end if;

    execute format(
        'update public.%I set %I=$1 where %I::text=$2',
        p_table,p_column,p_column
    ) using p_new_id,p_old_id;

    get diagnostics v_count=row_count;
    return v_count;
end;
$$;

create or replace function public.pc_merge_canonical_object(
    p_object_type text,
    p_survivor_id text,
    p_duplicate_id text,
    p_delete_duplicate boolean default true,
    p_notes text default null
)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_type text:=lower(p_object_type);
    v_survivor_name text;
    v_duplicate_name text;
    v_rel integer:=0;
    v_links integer:=0;
    v_direct integer:=0;
    v_deleted boolean:=false;
    r record;
begin
    if v_type='vessel' then v_type:='mobile_asset'; end if;

    if p_survivor_id=p_duplicate_id then
        raise exception 'Survivor and duplicate IDs are the same';
    end if;

    if not pc_object_exists(v_type,p_survivor_id) then
        raise exception 'Survivor % % does not exist',v_type,p_survivor_id;
    end if;
    if not pc_object_exists(v_type,p_duplicate_id) then
        raise exception 'Duplicate % % does not exist',v_type,p_duplicate_id;
    end if;

    v_survivor_name:=pc_object_name(v_type,p_survivor_id);
    v_duplicate_name:=pc_object_name(v_type,p_duplicate_id);

    -- Preserve duplicate spelling/name as alias.
    if nullif(trim(v_duplicate_name),'') is not null then
        insert into pc_identity_aliases_v2(object_type,canonical_id,alias_name,alias_type,metadata)
        values (
            v_type,
            p_survivor_id,
            v_duplicate_name,
            'merged_duplicate',
            jsonb_build_object('merged_from_id',p_duplicate_id)
        )
        on conflict (object_type,canonical_id,normalized_alias) do nothing;
    end if;

    -- Rewrite or collapse pc_relationships rows one at a time to avoid unique-key collisions.
    for r in
        select relationship_id,source_type,source_id,relationship_type,target_type,target_id
        from pc_relationships
        where (
            lower(source_type::text) in (
                case v_type when 'mobile_asset' then 'mobile_asset' else v_type end,
                case v_type when 'mobile_asset' then 'vessel' else v_type end
            )
            and source_id::text=p_duplicate_id
        )
        or (
            lower(target_type::text) in (
                case v_type when 'mobile_asset' then 'mobile_asset' else v_type end,
                case v_type when 'mobile_asset' then 'vessel' else v_type end
            )
            and target_id::text=p_duplicate_id
        )
    loop
        -- If the rewritten edge already exists, delete the duplicate edge.
        if exists (
            select 1 from pc_relationships x
            where x.relationship_id<>r.relationship_id
              and lower(x.source_type::text)=lower(r.source_type::text)
              and x.source_id::text =
                    case when r.source_id::text=p_duplicate_id then p_survivor_id else r.source_id::text end
              and lower(x.relationship_type::text)=lower(r.relationship_type::text)
              and lower(x.target_type::text)=lower(r.target_type::text)
              and x.target_id::text =
                    case when r.target_id::text=p_duplicate_id then p_survivor_id else r.target_id::text end
        ) then
            delete from pc_relationships where relationship_id=r.relationship_id;
        else
            update pc_relationships
            set source_id = case when source_id::text=p_duplicate_id then p_survivor_id else source_id::text end,
                target_id = case when target_id::text=p_duplicate_id then p_survivor_id else target_id::text end
            where relationship_id=r.relationship_id;
        end if;
        v_rel:=v_rel+1;
    end loop;

    -- Rewrite or collapse event links.
    for r in
        select event_link_id,event_id,linked_type,linked_id,relationship
        from pc_event_links
        where lower(linked_type::text) in (
            case v_type when 'mobile_asset' then 'mobile_asset' else v_type end,
            case v_type when 'mobile_asset' then 'vessel' else v_type end
        )
          and linked_id::text=p_duplicate_id
    loop
        if exists (
            select 1 from pc_event_links x
            where x.event_link_id<>r.event_link_id
              and x.event_id::text=r.event_id::text
              and lower(x.linked_type::text)=lower(r.linked_type::text)
              and x.linked_id::text=p_survivor_id
              and coalesce(lower(x.relationship::text),'')=coalesce(lower(r.relationship::text),'')
        ) then
            delete from pc_event_links where event_link_id=r.event_link_id;
        else
            update pc_event_links
            set linked_id=p_survivor_id
            where event_link_id=r.event_link_id;
        end if;
        v_links:=v_links+1;
    end loop;

    -- Common direct references.
    if v_type='entity' then
        v_direct:=v_direct + pc_rewrite_direct_reference('pc_assets','owner_entity_id',p_duplicate_id,p_survivor_id);
        v_direct:=v_direct + pc_rewrite_direct_reference('pc_assets','operator_entity_id',p_duplicate_id,p_survivor_id);
        v_direct:=v_direct + pc_rewrite_direct_reference('pc_mobile_assets','owner_entity_id',p_duplicate_id,p_survivor_id);
        v_direct:=v_direct + pc_rewrite_direct_reference('pc_mobile_assets','operator_entity_id',p_duplicate_id,p_survivor_id);
        v_direct:=v_direct + pc_rewrite_direct_reference('pc_mobile_assets','manager_entity_id',p_duplicate_id,p_survivor_id);
    end if;

    -- Rewrite ingestion key maps so old workbook IDs now point to the survivor.
    if to_regclass('public.pc_ingestion_key_map') is not null then
        update pc_ingestion_key_map
        set canonical_id=p_survivor_id, updated_at=now()
        where object_type in (
            v_type,
            case when v_type='mobile_asset' then 'vessel' else v_type end
        )
          and canonical_id=p_duplicate_id;
    end if;

    if p_delete_duplicate then
        case v_type
          when 'entity' then delete from pc_entities where entity_id::text=p_duplicate_id;
          when 'asset' then delete from pc_assets where asset_id::text=p_duplicate_id;
          when 'mobile_asset' then delete from pc_mobile_assets where mobile_asset_id::text=p_duplicate_id;
          when 'event' then delete from pc_events where event_id::text=p_duplicate_id;
          else raise exception 'Unsupported merge type: %',v_type;
        end case;
        v_deleted:=true;
    end if;

    insert into pc_canonical_merge_audit(
        object_type,survivor_id,duplicate_id,survivor_name,duplicate_name,
        rewritten_relationships,rewritten_event_links,rewritten_direct_refs,
        duplicate_deleted,notes
    )
    values(
        v_type,p_survivor_id,p_duplicate_id,v_survivor_name,v_duplicate_name,
        v_rel,v_links,v_direct,v_deleted,p_notes
    );

    return jsonb_build_object(
        'status','OK',
        'object_type',v_type,
        'survivor_id',p_survivor_id,
        'duplicate_id',p_duplicate_id,
        'survivor_name',v_survivor_name,
        'duplicate_name',v_duplicate_name,
        'relationships_rewritten',v_rel,
        'event_links_rewritten',v_links,
        'direct_refs_rewritten',v_direct,
        'duplicate_deleted',v_deleted
    );
end;
$$;

grant execute on function public.pc_merge_canonical_object(text,text,text,boolean,text) to authenticated;
grant select on public.pc_canonical_merge_audit to authenticated;

commit;

-- Example ONLY after reviewing duplicate candidates:
-- select public.pc_merge_canonical_object(
--   'asset',
--   '<SURVIVOR_ZAYED_PORT_ASSET_ID>',
--   '<DUPLICATE_ZAYAD_PORT_ASSET_ID>',
--   true,
--   'Confirmed duplicate during canonical hygiene review'
-- );
