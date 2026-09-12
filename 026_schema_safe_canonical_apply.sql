-- Power & Corridors Trade System
-- 026_schema_safe_canonical_apply.sql
-- Exposes the live PostgreSQL column set for canonical apply so Power Admin can
-- strip non-schema AI research attributes before PostgREST insert/upsert.
-- No canonical business data is modified.

begin;

create or replace function pc_get_table_write_columns(
    p_table_name text
)
returns jsonb
language plpgsql
security definer
set search_path=public
as $$
declare
    v_cols jsonb;
begin
    if coalesce(trim(p_table_name),'')='' then
        raise exception 'p_table_name is required';
    end if;

    if not exists (
        select 1
        from information_schema.tables
        where table_schema='public'
          and table_name=p_table_name
          and table_type='BASE TABLE'
    ) then
        raise exception 'Unknown public base table: %',p_table_name;
    end if;

    select jsonb_agg(column_name order by ordinal_position)
      into v_cols
      from information_schema.columns
     where table_schema='public'
       and table_name=p_table_name;

    return coalesce(v_cols,'[]'::jsonb);
end;
$$;

comment on function pc_get_table_write_columns(text) is
'Returns the live public-table column names used by Power Admin to prevent PostgREST PGRST204 errors from research attributes that are not canonical columns.';

commit;
