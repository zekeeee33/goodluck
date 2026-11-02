-- Repair route and rate fields on historical trips imported before route
-- matching was available. Apply after the route/rate and truck/trailer migrations.

begin;

with trip_routes as (
    select
        trip.id as trip_id,
        route.id as route_id,
        route.route_number,
        route.route_pair,
        coalesce(trip.pallet_capacity, trailer.pallet_capacity, load_capacity.capacity)
            as pallet_capacity,
        case
            when trip.truck_route_rate is null then rate.id
            else null
        end as rate_id,
        case
            when trip.truck_route_rate is null then rate.hauling_rate
            else null
        end as hauling_rate
    from public.trips as trip
    left join public.trailers as trailer
        on trailer.id = trip.trailer_id
    cross join lateral (
        select case
            when count(distinct capacity) = 1 then min(capacity)
            else null
        end as capacity
        from (
            select captures.parts[1]::integer as capacity
            from regexp_matches(
                coalesce(trip.load_details, ''),
                '(?:^|[^0-9])(24|36|46)[[:space:]]*P(?:[^A-Z]|$)',
                'gi'
            ) as captures(parts)
        ) as explicit_capacities
    ) as load_capacity
    join public.truck_routes as route
        on route.active is not false
       and route.origin_code = case
            when upper(regexp_replace(trim(trip.origin), '[[:space:]]+', ' ', 'g'))
                in ('GENSAN', 'GENSAN DISTRIBUTION CENTER') then 'GENSAN'
            when upper(regexp_replace(trim(trip.origin), '[[:space:]]+', ' ', 'g'))
                in ('DAV1', 'DAVAO BOTTLING PLANT 1') then 'DAV1'
            when upper(regexp_replace(trim(trip.origin), '[[:space:]]+', ' ', 'g'))
                in ('DAV2', 'DAVAO BOTTLING PLANT 2') then 'DAV2'
            when upper(regexp_replace(trim(trip.origin), '[[:space:]]+', ' ', 'g'))
                in ('PLAS', 'PLAS ASTORGA') then 'PLAS'
            else null
        end
       and route.destination_code = case
            when upper(regexp_replace(trim(trip.destination), '[[:space:]]+', ' ', 'g'))
                in ('GENSAN', 'GENSAN DISTRIBUTION CENTER') then 'GENSAN'
            when upper(regexp_replace(trim(trip.destination), '[[:space:]]+', ' ', 'g'))
                in ('DAV1', 'DAVAO BOTTLING PLANT 1') then 'DAV1'
            when upper(regexp_replace(trim(trip.destination), '[[:space:]]+', ' ', 'g'))
                in ('DAV2', 'DAVAO BOTTLING PLANT 2') then 'DAV2'
            when upper(regexp_replace(trim(trip.destination), '[[:space:]]+', ' ', 'g'))
                in ('PLAS', 'PLAS ASTORGA') then 'PLAS'
            else null
        end
    left join lateral (
        select configured_rate.id, configured_rate.hauling_rate
        from public.truck_route_rates as configured_rate
        where configured_rate.route_id = route.id
          and configured_rate.pallet_capacity = coalesce(
              trip.pallet_capacity,
              trailer.pallet_capacity,
              load_capacity.capacity
          )
          and configured_rate.active is not false
          and configured_rate.hauling_rate is not null
        order by configured_rate.id
        limit 1
    ) as rate on true
)
update public.trips as trip
set route_id = coalesce(trip.route_id, resolved.route_id),
    route_number = coalesce(trip.route_number, resolved.route_number),
    route_pair = coalesce(trip.route_pair, resolved.route_pair),
    pallet_capacity = coalesce(trip.pallet_capacity, resolved.pallet_capacity),
    truck_route_rate_id = coalesce(trip.truck_route_rate_id, resolved.rate_id),
    truck_route_rate = coalesce(trip.truck_route_rate, resolved.hauling_rate),
    trip_rate_review_required = case
        when resolved.rate_id is not null then false
        else trip.trip_rate_review_required
    end
from trip_routes as resolved
where trip.id = resolved.trip_id
  and (
      trip.route_id is null
      or trip.route_number is null
      or trip.route_pair is null
      or (trip.pallet_capacity is null and resolved.pallet_capacity is not null)
      or (
          trip.truck_route_rate is null
          and resolved.rate_id is not null
      )
  );

commit;
