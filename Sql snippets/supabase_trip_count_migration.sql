begin;

lock table public.trips in access exclusive mode;

alter table public.trips
    add column if not exists trip_count bigint;

do $$
declare
    has_created_at boolean;
begin
    select exists (
        select 1
        from information_schema.columns
        where table_schema = 'public'
          and table_name = 'trips'
          and column_name = 'created_at'
    ) into has_created_at;

    if has_created_at then
        execute $sql$
            with ranked_trips as (
                select id,
                       row_number() over (
                           order by created_at asc nulls last, id asc
                       ) + coalesce(
                           (select max(trip_count) from public.trips), 0
                       ) as assigned_trip_count
                from public.trips
                where trip_count is null
            )
            update public.trips as trip
            set trip_count = ranked_trips.assigned_trip_count
            from ranked_trips
            where trip.id = ranked_trips.id
        $sql$;
    else
        execute $sql$
            with ranked_trips as (
                select id,
                       row_number() over (order by id asc) + coalesce(
                           (select max(trip_count) from public.trips), 0
                       ) as assigned_trip_count
                from public.trips
                where trip_count is null
            )
            update public.trips as trip
            set trip_count = ranked_trips.assigned_trip_count
            from ranked_trips
            where trip.id = ranked_trips.id
        $sql$;
    end if;
end;
$$;

alter table public.trips
    alter column trip_count set not null;

create unique index if not exists trips_trip_count_key
    on public.trips(trip_count);

create table if not exists public.trip_count_counters (
    counter_name text primary key check (counter_name = 'trips'),
    last_value bigint not null check (last_value >= 0)
);

insert into public.trip_count_counters(counter_name, last_value)
select 'trips', coalesce(max(trip_count), 0)
from public.trips
on conflict (counter_name) do update
set last_value = greatest(
    public.trip_count_counters.last_value,
    excluded.last_value
);

revoke all on table public.trip_count_counters from public, anon, authenticated;

create or replace function public.assign_trip_count()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
    if tg_op = 'INSERT' then
        update public.trip_count_counters
        set last_value = last_value + 1
        where counter_name = 'trips'
        returning last_value into new.trip_count;

        if new.trip_count is null then
            raise exception 'Trip count counter is not initialized';
        end if;
    elsif new.trip_count is distinct from old.trip_count then
        raise exception 'Trip count is permanent and cannot be changed';
    end if;

    return new;
end;
$$;

revoke all on function public.assign_trip_count() from public, anon, authenticated;

drop trigger if exists trips_assign_trip_count on public.trips;
create trigger trips_assign_trip_count
before insert or update on public.trips
for each row execute function public.assign_trip_count();

commit;
