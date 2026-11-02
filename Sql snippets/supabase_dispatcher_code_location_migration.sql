-- Grant active dispatcher profiles D1-D6 access to DAV1-DAV6.
-- This migration is safe to rerun. It updates only these mapped assignments.
-- Run after supabase_location_dispatch_migration.sql.

begin;

do $$
declare
    profile_table text;
    profile_table_count integer;
begin
    select min(candidate.table_name), count(*)::integer
    into profile_table, profile_table_count
    from (
        select columns.table_name
        from information_schema.columns as columns
        join information_schema.tables as tables
          on tables.table_schema = columns.table_schema
         and tables.table_name = columns.table_name
         and tables.table_type = 'BASE TABLE'
        where columns.table_schema = 'public'
          and columns.column_name in ('id', 'email', 'role', 'dispatcher_code', 'status')
        group by columns.table_name
        having count(*) = 5
           and bool_and(
               case
                   when columns.column_name = 'id' then columns.data_type = 'uuid'
                   else columns.data_type in ('text', 'character varying', 'character')
               end
           )
    ) as candidate;

    if profile_table_count = 0 then
        raise exception
            'Could not find a public profile table with UUID id, email, role, dispatcher_code, and status columns';
    elsif profile_table_count > 1 then
        raise exception
            'Found multiple matching public profile tables; simplify the schema or specify the profile table explicitly';
    end if;

    execute format($map_locations$
        insert into public.dispatch_locations (id, name)
        select 'DAV' || substring(upper(trim(profile.dispatcher_code)) from 2),
               'DAV' || substring(upper(trim(profile.dispatcher_code)) from 2)
        from public.%I as profile
        where lower(trim(profile.role)) = 'dispatcher'
          and lower(trim(profile.status)) = 'active'
          and upper(trim(profile.dispatcher_code)) ~ '^D[1-6]$'
        on conflict (id) do nothing
    $map_locations$, profile_table);

    execute format($map_assignments$
        insert into public.dispatcher_location_assignments (
            user_id, location_id, can_depart, can_arrive
        )
        select auth_user.id,
               'DAV' || substring(upper(trim(profile.dispatcher_code)) from 2),
               true, true
        from public.%I as profile
        join auth.users as auth_user on auth_user.id = profile.id
        join public.dispatch_locations as location
          on location.id = 'DAV' || substring(upper(trim(profile.dispatcher_code)) from 2)
         and location.active
        where lower(trim(profile.role)) = 'dispatcher'
          and lower(trim(profile.status)) = 'active'
          and upper(trim(profile.dispatcher_code)) ~ '^D[1-6]$'
        on conflict (user_id, location_id) do update set
            can_depart = excluded.can_depart,
            can_arrive = excluded.can_arrive,
            updated_at = now()
    $map_assignments$, profile_table);
end;
$$;

commit;

select
    auth_user.email,
    assignment.location_id,
    assignment.can_depart,
    assignment.can_arrive
from public.dispatcher_location_assignments as assignment
join auth.users as auth_user on auth_user.id = assignment.user_id
where assignment.location_id ~ '^DAV[1-6]$'
order by assignment.location_id, auth_user.email;
