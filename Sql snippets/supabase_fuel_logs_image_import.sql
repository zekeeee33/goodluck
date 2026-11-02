-- Import the fuel amounts transcribed from the October 25-29, 2026 image.
-- Match trips by ISM number and assign a registered truck from the supplied list.
-- Rows without an ISM number are intentionally excluded for manual matching.

begin;

create temporary table fuel_logs_image_import (
    ism_no text primary key,
    logged_on date not null,
    vehicle_plate text not null,
    fuel_type text not null,
    actual_expense numeric(12, 2) not null check (actual_expense >= 0),
    remarks text
) on commit drop;

insert into fuel_logs_image_import
    (ism_no, logged_on, vehicle_plate, fuel_type, actual_expense, remarks)
values
    ('32098501', '2026-10-25', 'MUA973', 'diesel', 9350.00, null),
    ('32083031', '2026-10-25', 'MUA973', 'diesel', 9350.00, null),
    ('32098502', '2026-10-25', 'MUB263', 'diesel', 8882.50, null),
    ('32083033', '2026-10-25', 'MUB263', 'diesel', 8882.50, null),
    ('32090536', '2026-10-25', 'MUB263', 'diesel', 8882.50, null),
    ('32097573', '2026-10-26', '173827', 'diesel', 10285.00, null),
    ('32097540', '2026-10-26', '173827', 'diesel', 10285.00, null),
    ('32084017', '2026-10-26', 'MUA973', 'diesel', 8882.50, null),
    ('32097574', '2026-10-26', 'MUB282', 'diesel', 8882.50, null),
    ('32083038', '2026-10-26', 'MUB282', 'diesel', 8882.50, null),
    ('32084018', '2026-10-26', 'MUB282', 'diesel', 9817.50, null),
    ('32057480', '2026-10-26', 'MUB109', 'diesel', 10752.50, null),
    ('32098553', '2026-10-26', 'MUA538', 'diesel', 9817.50, null),
    ('32090542', '2026-10-26', 'MUB109', 'diesel', 9817.50, null),
    ('32090247', '2026-10-26', 'MUA551', 'diesel', 9817.50, null),
    ('32083052', '2026-10-26', 'MUA551', 'diesel', 9817.50, null),
    ('32104952', '2026-10-27', 'MUA551', 'diesel', 10752.50, null),
    ('32083600', '2026-10-27', 'MUA538', 'diesel', 9817.50, null),
    ('32103073', '2026-10-27', 'MUB106', 'diesel', 9817.50, null),
    ('32083053', '2026-10-27', 'MUB106', 'diesel', 9817.50, null),
    ('32082185', '2026-10-27', 'MUB106', 'diesel', 9817.50, null),
    ('32057481', '2026-10-27', 'MUA508', 'diesel', 9817.50, null),
    ('32083059', '2026-10-27', 'MUB106', 'diesel', 9817.50, null),
    ('32082183', '2026-10-27', 'MUA508', 'diesel', 9817.50, null),
    ('32083063', '2026-10-27', 'MUA508', 'diesel', 9817.50, null),
    ('32104954', '2026-10-27', 'MUB106', 'diesel', 9817.50, null),
    ('32104953', '2026-10-27', 'MUA508', 'diesel', 9817.50, null),
    ('32111511', '2026-10-27', 'MUA548', 'diesel', 9817.50, null),
    ('32060398', '2026-10-27', 'MUA528', 'diesel', 9817.50, null),
    ('32083076', '2026-10-27', 'MUA548', 'diesel', 9817.50, null),
    ('32111513', '2026-10-27', 'MUA528', 'diesel', 9817.50, null),
    ('32083077', '2026-10-27', 'MUA528', 'diesel', 9817.50, null),
    ('32111514', '2026-10-27', 'MUA528', 'diesel', 9817.50, null),
    ('32083080', '2026-10-27', 'MUA548', 'diesel', 10285.00, null),
    ('32104955', '2026-10-27', 'MUA548', 'diesel', 9817.50, null),
    ('32104956', '2026-10-28', 'MUA528', 'diesel', 9817.50, null),
    ('32106135', '2026-10-28', 'MUB109', 'diesel', 9817.50, null),
    ('32083092', '2026-10-28', 'MUB109', 'diesel', 9817.50, null),
    ('32111515', '2026-10-28', 'MUB109', 'diesel', 9817.50, null),
    ('32106138', '2026-10-28', 'MUA551', 'diesel', 9817.50, null),
    ('32083093', '2026-10-28', 'MUA551', 'diesel', 9817.50, null),
    ('32111516', '2026-10-28', 'MUA551', 'diesel', 9817.50, null),
    ('32083100', '2026-10-28', 'MUB109', 'diesel', 9817.50, null),
    ('32083103', '2026-10-28', 'MUA551', 'diesel', 10285.00, null),
    ('32112016', '2026-10-28', 'MUB109', 'diesel', 10285.00, null),
    ('32112017', '2026-10-28', 'MUA551', 'diesel', 9817.50, null),
    ('32114436', '2026-10-29', '173827', 'diesel', 9817.50, null),
    ('32097551', '2026-10-29', '173827', 'diesel', 9817.50, null),
    ('32114532', '2026-10-29', 'MUB106', 'diesel', 9817.50, null),
    ('32083110', '2026-10-29', 'MUB106', 'diesel', 9817.50, null),
    ('32111541', '2026-10-29', 'MUB106', 'diesel', 9817.50, null),
    ('32115044', '2026-10-29', 'MUA508', 'diesel', 9817.50, null),
    ('32083118', '2026-10-29', 'MUA508', 'diesel', 9817.50, null),
    ('32111542', '2026-10-29', 'MUA508', 'diesel', 10752.50, null),
    ('32083124', '2026-10-29', 'MUB106', 'diesel', 10752.50, null),
    ('32083126', '2026-10-29', 'MUA508', 'diesel', 10752.50, null),
    ('32114438', '2026-10-29', 'MUA518', 'diesel', 10752.50, null),
    ('32083121', '2026-10-29', 'MUA518', 'diesel', 9817.50, null),
    ('32111544', '2026-10-29', 'MUA518', 'diesel', 10752.50, null),
    ('32117868', '2026-10-29', 'MUA518', 'diesel', 10752.50, null),
    ('32112019', '2026-10-29', 'MUB106', 'diesel', 9817.50, null),
    ('32120549', '2026-10-29', 'MUA508', 'diesel', 10752.50, null);

create temporary table fuel_logs_image_import_matches on commit drop as
select
    source.ism_no,
    resolved_trip.id as trip_id,
    resolved_trip.truck_id,
    resolved_trip.vehicle_id
from fuel_logs_image_import as source
join lateral (
    select trip.id, trip.truck_id, trip.vehicle_id
    from public.trips as trip
    where trip.ism_no = source.ism_no
      and (
          (
              select count(*)
              from public.trips as candidate
              where candidate.ism_no = source.ism_no
          ) = 1
          or (
              (
                  select count(*)
                  from public.trips as candidate
                  where candidate.ism_no = source.ism_no
                    and upper(trim(coalesce(candidate.plate_no, ''))) =
                        upper(trim(source.vehicle_plate))
              ) = 1
              and upper(trim(coalesce(trip.plate_no, ''))) =
                  upper(trim(source.vehicle_plate))
          )
          or (
              not exists (
                  select 1
                  from public.trips as candidate
                  where candidate.ism_no = source.ism_no
                    and upper(trim(coalesce(candidate.plate_no, ''))) =
                        upper(trim(source.vehicle_plate))
              )
              and (
                  select count(*)
                  from public.trips as candidate
                  where candidate.ism_no = source.ism_no
                    and candidate.trip_date = source.logged_on
              ) = 1
              and trip.trip_date = source.logged_on
          )
      )
) as resolved_trip on true;

-- Pick one supplied truck per row; retain an existing trip assignment on reruns.
create temporary table fuel_logs_image_import_vehicles on commit drop as
select
    source.ism_no,
    coalesce(existing.vehicle_id, selected_vehicle.id) as vehicle_id
from fuel_logs_image_import as source
join fuel_logs_image_import_matches as matched_trip
  on matched_trip.ism_no = source.ism_no
left join public.fuel_logs as existing
  on existing.trip_id = matched_trip.trip_id
left join lateral (
    select vehicle.id
    from public.vehicles as vehicle
    join (
        values
            (2::bigint, 'UPH293'),
            (3::bigint, 'UBX899'),
            (4::bigint, 'EVV104'),
            (5::bigint, 'MEB734'),
            (6::bigint, 'UHZ217'),
            (7::bigint, 'GKB272'),
            (8::bigint, 'UPU446'),
            (9::bigint, 'MVG983'),
            (10::bigint, 'UJZ316'),
            (11::bigint, 'TBN276'),
            (15::bigint, 'LAS5593'),
            (16::bigint, 'LAS5596'),
            (17::bigint, 'LAO7098'),
            (18::bigint, 'LAO7202'),
            (19::bigint, 'LAO7425'),
            (20::bigint, 'LAS2006'),
            (21::bigint, 'LAS2007'),
            (22::bigint, 'NJI1502'),
            (23::bigint, 'NJI1511'),
            (24::bigint, 'LAQ8291')
    ) as supplied_vehicle(id, plate_number)
      on vehicle.id = supplied_vehicle.id
     and upper(trim(vehicle.plate_number)) =
         upper(trim(supplied_vehicle.plate_number))
    order by random()
    limit 1
) as selected_vehicle on true;

do $$
declare
    unresolved_count integer;
    mismatch_count integer;
begin
    select count(*) into unresolved_count
    from fuel_logs_image_import as source
    where (
        select count(*)
        from fuel_logs_image_import_matches as matched_trip
        where matched_trip.ism_no = source.ism_no
    ) <> 1;
    if unresolved_count > 0 then
        raise exception
            'Fuel import stopped: % rows do not resolve to exactly one trip by ISM, plate, and date.',
            unresolved_count;
    end if;

    select count(*) into unresolved_count
    from fuel_logs_image_import as source
    where (
        select count(*)
        from fuel_logs_image_import_vehicles as assigned
        where assigned.ism_no = source.ism_no
          and assigned.vehicle_id is not null
    ) <> 1;
    if unresolved_count > 0 then
        raise exception
            'Fuel import stopped: % rows could not be assigned a registered truck from the supplied list.',
            unresolved_count;
    end if;

    select count(*) into mismatch_count
    from fuel_logs_image_import as source
    join fuel_logs_image_import_matches as matched_trip
      on matched_trip.ism_no = source.ism_no
    join fuel_logs_image_import_vehicles as assigned
      on assigned.ism_no = source.ism_no
    join public.vehicles as vehicle
      on vehicle.id = assigned.vehicle_id
    join public.fuel_logs as existing on existing.trip_id = matched_trip.trip_id
    where existing.actual_expense is distinct from source.actual_expense
       or existing.logged_on is distinct from source.logged_on;
    if mismatch_count > 0 then
        raise exception
            'Fuel import stopped: % trips already have a different linked fuel log. Review those records before importing.',
            mismatch_count;
    end if;
end;
$$;

insert into public.fuel_logs (
    vehicle_id,
    fuel_type,
    quantity,
    price_per_liter,
    total_cost,
    logged_on,
    trip_id,
    actual_expense,
    remarks
)
select
    assigned.vehicle_id,
    source.fuel_type,
    105.00,
    null,
    null,
    source.logged_on,
    matched_trip.trip_id,
    source.actual_expense,
    source.remarks
from fuel_logs_image_import as source
join fuel_logs_image_import_matches as matched_trip
  on matched_trip.ism_no = source.ism_no
join fuel_logs_image_import_vehicles as assigned
  on assigned.ism_no = source.ism_no
on conflict (trip_id) where trip_id is not null
do update set quantity = excluded.quantity;

commit;
