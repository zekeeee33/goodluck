-- Run after supabase_route_trip_rate_migration.sql.
-- Adds the approved hauling rate for 50-pallet trailers on DAV2 -> PLAS
-- and backfills matching historical trips that have no saved hauling rate.

begin;

do $$
begin
    if not exists (
        select 1
        from public.truck_routes
        where origin_code = 'DAV2'
          and destination_code = 'PLAS'
    ) then
        raise exception 'Route DAV2 -> PLAS is not configured';
    end if;
end;
$$;

insert into public.truck_route_rates (
    origin_code,
    destination_code,
    pallet_capacity,
    hauling_rate,
    active,
    route_id
)
select
    route.origin_code,
    route.destination_code,
    50,
    3055.50,
    true,
    route.id
from public.truck_routes as route
where route.origin_code = 'DAV2'
  and route.destination_code = 'PLAS'
on conflict (origin_code, destination_code, pallet_capacity)
do update set
    hauling_rate = excluded.hauling_rate,
    active = excluded.active,
    route_id = excluded.route_id,
    updated_at = now();

with matching_trips as (
    select
        trip.id as trip_id,
        route.id as route_id,
        route.route_number,
        route.route_pair,
        rate.id as rate_id,
        rate.hauling_rate
    from public.trips as trip
    join public.trailers as trailer
        on trailer.id = trip.trailer_id
    join public.truck_routes as route
        on route.origin_code = 'DAV2'
       and route.destination_code = 'PLAS'
       and route.active is not false
    join public.truck_route_rates as rate
        on rate.route_id = route.id
       and rate.pallet_capacity = 50
       and rate.active is not false
       and rate.hauling_rate is not null
    where trip.truck_route_rate is null
      and coalesce(trip.pallet_capacity, trailer.pallet_capacity) = 50
      and case
            when upper(regexp_replace(trim(trip.origin), '[[:space:]]+', ' ', 'g'))
                in ('DAV2', 'DAVAO BOTTLING PLANT 2') then 'DAV2'
            else null
          end = route.origin_code
      and case
            when upper(regexp_replace(trim(trip.destination), '[[:space:]]+', ' ', 'g'))
                in ('PLAS', 'PLAS ASTORGA') then 'PLAS'
            else null
          end = route.destination_code
)
update public.trips as trip
set route_id = coalesce(trip.route_id, matching.route_id),
    route_number = coalesce(trip.route_number, matching.route_number),
    route_pair = coalesce(trip.route_pair, matching.route_pair),
    pallet_capacity = coalesce(trip.pallet_capacity, 50),
    truck_route_rate_id = matching.rate_id,
    truck_route_rate = matching.hauling_rate,
    trip_rate_review_required = false
from matching_trips as matching
where trip.id = matching.trip_id
  and trip.truck_route_rate is null;

commit;
