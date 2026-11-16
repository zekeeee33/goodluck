-- Import/repair the supplied trips for 2026-11-14 through 2026-11-16.
-- Apply after the route/rate and truck/trailer migrations.
--
-- Truck and trailer plates are resolved to registry IDs when registered; the
-- source truck plate is always retained in plate_no. Rates use the registered
-- trailer capacity when available, otherwise the stated manifest pallet count.
-- Trips to GENSAN are FULL (36 pallets); trips from GENSAN are EMPTY. Empty
-- loads with no usable capacity or missing configured rates remain flagged
-- for review.
--
-- Safe to rerun: matching rows are updated by date, ISM number, and direction;
-- rows without a match are inserted.

begin;

create temporary table trip_import_source (
    trip_date date not null,
    ism_no text not null,
    shipment_date date not null,
    time_in time without time zone,
    time_out time without time zone,
    origin text not null,
    destination text not null,
    route text not null,
    load_details text,
    notes text,
    truck_plate text not null,
    driver_name text not null,
    trailer_plate text not null,
    manifest_pallet_capacity integer
) on commit drop;

insert into trip_import_source (
    trip_date, ism_no, shipment_date, time_in, time_out,
    origin, destination, route, load_details, notes,
    truck_plate, driver_name, trailer_plate, manifest_pallet_capacity
) values
    ('2026-11-14', '32206741', '2026-11-14', '15:20', null,
     'GENSAN', 'PLAS', 'GENSAN to PLAS', 'EMPTY', null,
     'LAQ8291', 'JOVANY MAYORES', 'MUA508', 46),
    ('2026-11-14', '32187669', '2026-11-14', '19:15', '16:25',
     'PLAS', 'DAV2', 'PLAS to DAV2', '46P COKE LITRO', 'DR: 0044256',
     'LAQ8291', 'JOVANY MAYORES', 'MUA508', 46),
    ('2026-11-14', '32204068', '2026-11-14', '15:40', null,
     'GENSAN', 'PLAS', 'GENSAN to PLAS', 'EMPTY', null,
     'LAO7425', 'RICHARD VALERA', 'MUB106', 46),
    ('2026-11-14', '32187670', '2026-11-14', '19:20', '17:05',
     'PLAS', 'DAV2', 'PLAS to DAV2', '46P COKE LITRO', 'DR: 0044257',
     'LAO7425', 'RICHARD VALERA', 'MUB106', 46),
    ('2026-11-14', '32206740', '2026-11-14', '16:10', null,
     'GENSAN', 'PLAS', 'GENSAN to PLAS', 'EMPTY', null,
     'LAO9202', 'JAMES NACION', 'MUA528', 46),
    ('2026-11-14', '32187671', '2026-11-14', '19:25', '17:50',
     'PLAS', 'DAV2', 'PLAS to DAV2', '46P COKE LITRO', 'DR: 0044258',
     'LAO9202', 'JAMES NACION', 'MUA528', 46),
    ('2026-11-14', '32172402', '2026-11-14', '16:40', null,
     'GENSAN', 'PLAS', 'GENSAN to PLAS', 'EMPTY', null,
     'LAS5593', 'DANDY CABADA', 'MUB109', null),
    ('2026-11-14', '32187673', '2026-11-14', '19:30', '18:15',
     'PLAS', 'DAV2', 'PLAS to DAV2', '46P COKE LITRO', 'DR: 0044260',
     'LAS5593', 'DANDY CABADA', 'MUB109', 46),
    ('2026-11-14', '32172404', '2026-11-14', '16:25', null,
     'GENSAN', 'PLAS', 'GENSAN to PLAS', 'EMPTY', null,
     'LAS2007', 'REY MADAMBA', 'MUA538', null),
    ('2026-11-14', '32187674', '2026-11-14', '19:35', '18:45',
     'PLAS', 'DAV2', 'PLAS to DAV2', '36P COKE LITRO', 'DR: 0044261',
     'LAS2007', 'REY MADAMBA', 'MUA538', 36),
    ('2026-11-14', '32206469', '2026-11-14', '21:30', null,
     'GENSAN', 'DAV1', 'GENSAN to DAV1', 'EMPTY', null,
     'MAO5280', 'JUSEL CABAL', 'MUA973', 36),
    ('2026-11-14', '32207052', '2026-11-14', '23:35', null,
     'GENSAN', 'DAV1', 'GENSAN to DAV1', 'EMPTY', null,
     'NJI1511', 'JONATHAN MAMAC', 'MUA548', 36),
    ('2026-11-14', '32205361', '2026-11-14', null, '23:45',
     'DAV1', 'GENSAN', 'DAV1 to GENSAN', 'FULL (36 pallets)', null,
     'NJI1511', 'JONATHAN MAMAC', 'MUA548', 36),
    ('2026-11-14', '32205362', '2026-11-14', null, '23:00',
     'DAV1', 'GENSAN', 'DAV1 to GENSAN', 'FULL (36 pallets)', null,
     'MAO5280', 'JUSEL CABAL', 'MUA973', 36),
    ('2026-11-14', '32187675', '2026-11-14', '11:35', '23:00',
     'PLAS', 'DAV2', 'PLAS to DAV2', '46P COKE LITRO', null,
     'LAS2006', 'NOLITO SAMARCA', 'MUB289', 46),

    ('2026-11-15', '32186572', '2026-11-15', null, '03:00',
     'DAV2', 'GENSAN', 'DAV2 to GENSAN', 'FULL (36 pallets)', null,
     'LAQ8291', 'JOVANY MAYORES', 'MUA508', 36),
    ('2026-11-15', '32198327', '2026-11-15', null, '04:15',
     'DAV2', 'GENSAN', 'DAV2 to GENSAN', 'FULL (36 pallets)', null,
     'LAO7425', 'RICHARD VALERA', 'MUB106', 36),
    ('2026-11-15', '32198329', '2026-11-15', null, '05:15',
     'DAV2', 'GENSAN', 'DAV2 to GENSAN', 'FULL (36 pallets)', null,
     'LAS5593', 'DANDY CABADA', 'MUB109', 36),
    ('2026-11-15', '32198328', '2026-11-15', null, '06:40',
     'DAV2', 'GENSAN', 'DAV2 to GENSAN', 'FULL (36 pallets)', null,
     'LAO9202', 'JAMES NACION', 'MUA528', 36),
    ('2026-11-15', '32198315', '2026-11-15', null, '08:00',
     'DAV2', 'GENSAN', 'DAV2 to GENSAN', 'FULL (36 pallets)', null,
     'LAS2007', 'REY MADAMBA', 'MUA538', 36),
    ('2026-11-15', '32198343', '2026-11-15', null, '12:15',
     'DAV2', 'GENSAN', 'DAV2 to GENSAN', 'FULL (36 pallets)', null,
     'LAS2006', 'NOLITO SAMARCA', 'MUB289', 36),
    ('2026-11-15', '32212536', '2026-11-15', '11:35', null,
     'GENSAN', 'PLAS', 'GENSAN to PLAS', 'EMPTY', null,
     'NJI1511', 'JONATHAN MAMAC', 'MUA548', 46),
    ('2026-11-15', '32204127', '2026-11-15', '13:10', '12:50',
     'PLAS', 'DAV2', 'PLAS to DAV2', '46P COKE LITRO', 'DR: 0044272',
     'NJI1511', 'JONATHAN MAMAC', 'MUA548', 46),
    ('2026-11-15', '32198342', '2026-11-15', null, '14:35',
     'DAV2', 'GENSAN', 'DAV2 to GENSAN', 'FULL (36 pallets)', null,
     'NJI1511', 'JONATHAN MAMAC', 'MUA548', 36),

    ('2026-11-16', '32211072', '2026-11-16', '01:00', null,
     'GENSAN', 'DAV1', 'GENSAN to DAV1', 'EMPTY', null,
     'MVG293', 'JOVEN JAY BAING', 'MUB282', 36),
    ('2026-11-16', '32211071', '2026-11-16', '01:05', null,
     'GENSAN', 'DAV1', 'GENSAN to DAV1', 'EMPTY', null,
     'NJI1502', 'JAMES ARABELLA', 'MUB263', 36),
    ('2026-11-16', '32212529', '2026-11-16', null, '03:35',
     'DAV1', 'GENSAN', 'DAV1 to GENSAN', 'FULL (36 pallets)', null,
     'MVG293', 'JOVEN JAY BAING', 'MUB282', 36),
    ('2026-11-16', '32212528', '2026-11-16', null, '04:30',
     'DAV1', 'GENSAN', 'DAV1 to GENSAN', 'FULL (36 pallets)', null,
     'NJI1502', 'JAMES ARABELLA', 'MUB263', 36);

-- Repair the previously mistyped ISM number if the earlier import was run.
update public.trips as trip
set ism_no = '32187675'
where trip.trip_date = date '2026-11-14'
  and trip.ism_no = '3218675'
  and upper(trim(trip.origin)) = 'PLAS'
  and upper(trim(trip.destination)) = 'DAV2'
  and exists (
      select 1
      from public.trailers as trailer
      where trailer.id = trip.trailer_id
        and upper(regexp_replace(trim(trailer.plate_number), '[[:space:]]+', '', 'g')) = 'MUB289'
  );

create temporary table trip_import_resolved on commit drop as
select
    source.*,
    truck.id as vehicle_id,
    driver.id as driver_id,
    trailer.id as trailer_id,
    route.id as route_id,
    route.route_number,
    route.route_pair,
    coalesce(trailer.pallet_capacity, source.manifest_pallet_capacity)
        as resolved_pallet_capacity,
    rate.id as truck_route_rate_id,
    rate.hauling_rate as truck_route_rate
from trip_import_source as source
left join public.vehicles as truck
    on upper(regexp_replace(trim(truck.plate_number), '[[:space:]]+', '', 'g'))
       = upper(regexp_replace(trim(source.truck_plate), '[[:space:]]+', '', 'g'))
left join public.drivers as driver
    on upper(trim(driver.name)) = upper(trim(source.driver_name))
left join public.trailers as trailer
    on upper(regexp_replace(trim(trailer.plate_number), '[[:space:]]+', '', 'g'))
       = upper(regexp_replace(trim(source.trailer_plate), '[[:space:]]+', '', 'g'))
left join public.truck_routes as route
    on route.origin_code = source.origin
   and route.destination_code = source.destination
   and route.active is not false
left join public.truck_route_rates as rate
    on rate.route_id = route.id
   and rate.pallet_capacity = coalesce(
       trailer.pallet_capacity,
       source.manifest_pallet_capacity
   )
   and rate.active is not false
   and rate.hauling_rate is not null;

do $$
declare
    missing_trucks text;
    missing_trailers text;
    missing_routes text;
begin
    select string_agg(distinct truck_plate, ', ' order by truck_plate)
    into missing_trucks
    from trip_import_resolved
    where vehicle_id is null;

    select string_agg(distinct trailer_plate, ', ' order by trailer_plate)
    into missing_trailers
    from trip_import_resolved
    where trailer_id is null;

    select string_agg(
        distinct origin || ' -> ' || destination,
        ', ' order by origin || ' -> ' || destination
    )
    into missing_routes
    from trip_import_resolved
    where route_id is null;

    if missing_trucks is not null then
        raise warning
            'Truck plates not found in public.vehicles; trips will retain plate_no with a null truck registry ID: %',
            missing_trucks;
    end if;

    if missing_trailers is not null
       or missing_routes is not null then
        raise exception 'Trip import stopped. Missing trailers: %. Missing active routes: %.',
            coalesce(missing_trailers, 'none'),
            coalesce(missing_routes, 'none');
    end if;

    if exists (
        select 1
        from trip_import_source as source
        join public.trips as trip
          on trip.trip_date = source.trip_date
         and trip.ism_no = source.ism_no
         and upper(trim(trip.origin)) = upper(trim(source.origin))
         and upper(trim(trip.destination)) = upper(trim(source.destination))
        group by source.trip_date, source.ism_no, source.origin, source.destination
        having count(*) > 1
    ) then
        raise exception
            'Trip import stopped: multiple existing trips match a source row. Resolve those duplicates before importing.';
    end if;
end;
$$;

update public.trips as trip
set vehicle_id = resolved.vehicle_id,
    truck_id = resolved.vehicle_id,
    driver_id = resolved.driver_id,
    trailer_id = resolved.trailer_id,
    trip_date = resolved.trip_date,
    ism_no = resolved.ism_no,
    shipment_date = resolved.shipment_date,
    time_in = resolved.time_in,
    time_out = resolved.time_out,
    origin = resolved.origin,
    destination = resolved.destination,
    route = resolved.route,
    load_details = resolved.load_details,
    notes = resolved.notes,
    plate_no = resolved.truck_plate,
    driver_name = resolved.driver_name,
    route_id = resolved.route_id,
    route_number = resolved.route_number,
    route_pair = resolved.route_pair,
    pallet_capacity = resolved.resolved_pallet_capacity,
    truck_route_rate_id = resolved.truck_route_rate_id,
    truck_route_rate = resolved.truck_route_rate,
    trip_rate_review_required = (resolved.truck_route_rate_id is null),
    trailer_review_required = (resolved.resolved_pallet_capacity is null)
from trip_import_resolved as resolved
where trip.trip_date = resolved.trip_date
  and trip.ism_no = resolved.ism_no
  and upper(trim(trip.origin)) = upper(trim(resolved.origin))
  and upper(trim(trip.destination)) = upper(trim(resolved.destination));

insert into public.trips (
    vehicle_id, truck_id, driver_id, trailer_id,
    trip_date, ism_no, shipment_date, time_in, time_out,
    origin, destination, route, load_details, notes, plate_no, driver_name,
    route_id, route_number, route_pair, pallet_capacity,
    truck_route_rate_id, truck_route_rate,
    trip_rate_review_required, trailer_review_required
)
select
    resolved.vehicle_id, resolved.vehicle_id, resolved.driver_id, resolved.trailer_id,
    resolved.trip_date, resolved.ism_no, resolved.shipment_date,
    resolved.time_in, resolved.time_out, resolved.origin, resolved.destination,
    resolved.route, resolved.load_details, resolved.notes,
    resolved.truck_plate, resolved.driver_name,
    resolved.route_id, resolved.route_number, resolved.route_pair,
    resolved.resolved_pallet_capacity,
    resolved.truck_route_rate_id, resolved.truck_route_rate,
    (resolved.truck_route_rate_id is null),
    (resolved.resolved_pallet_capacity is null)
from trip_import_resolved as resolved
where not exists (
    select 1
    from public.trips as trip
    where trip.trip_date = resolved.trip_date
      and trip.ism_no = resolved.ism_no
      and upper(trim(trip.origin)) = upper(trim(resolved.origin))
      and upper(trim(trip.destination)) = upper(trim(resolved.destination))
);

-- Review this result after the import. Rows requiring review have no usable
-- capacity or no matching active configured route rate.
select
    trip.ism_no,
    trip.trip_date,
    trip.origin,
    trip.destination,
    trailer.plate_number as trailer_plate,
    trip.pallet_capacity,
    trip.truck_route_rate,
    trip.trip_rate_review_required,
    trip.trailer_review_required
from public.trips as trip
left join public.trailers as trailer on trailer.id = trip.trailer_id
join trip_import_source as source
  on source.trip_date = trip.trip_date
 and source.ism_no = trip.ism_no
 and upper(trim(source.origin)) = upper(trim(trip.origin))
 and upper(trim(source.destination)) = upper(trim(trip.destination))
order by trip.trip_date, trip.ism_no;

commit;
