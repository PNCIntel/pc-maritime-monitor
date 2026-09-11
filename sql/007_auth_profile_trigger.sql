-- Keep pc_profiles synchronized with Supabase Auth signups.
create or replace function public.pc_handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path=public
as $$
begin
  insert into public.pc_profiles(user_id,email,display_name,global_role,active)
  values(new.id,new.email,coalesce(new.raw_user_meta_data->>'full_name',new.raw_user_meta_data->>'name'),'user',true)
  on conflict(user_id) do update set email=excluded.email,updated_at=now();
  return new;
end;
$$;

drop trigger if exists pc_on_auth_user_created on auth.users;
create trigger pc_on_auth_user_created
after insert on auth.users
for each row execute procedure public.pc_handle_new_auth_user();
