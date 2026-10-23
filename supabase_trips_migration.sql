-- Expand public.trips to accept both application-created trips and the
-- shipment manifest CSV. This is additive and keeps all existing rows.
alter table public.trips
    add column if not exists record_date date,
    add column if not exists ism_no text,
    add column if not exists shipment_date date,
    add column if not exists time_in time without time zone,
    add column if not exists time_out time without time zone,
    add column if not exists origin text,
    add column if not exists destination text,
    add column if not exists plate_no text,
    add column if not exists load_details text,
    add column if not exists driver_name text,
    add column if not exists trip_fuel text;

update public.trips
set shipment_date = trip_date
where shipment_date is null;

alter table public.trips
    alter column shipment_date set default current_date,
    alter column shipment_date set not null,
    alter column vehicle_id drop not null,
    alter column driver_id drop not null,
    alter column route drop not null,
    alter column start_odometer drop not null,
    alter column end_odometer drop not null,
    alter column trip_date drop not null;

-- Preserve display data when an existing linked vehicle or driver is removed.
alter table public.trips drop constraint if exists trips_vehicle_id_fkey;
alter table public.trips
    add constraint trips_vehicle_id_fkey
    foreign key (vehicle_id) references public.vehicles(id) on delete set null;

alter table public.trips drop constraint if exists trips_driver_id_fkey;
alter table public.trips
    add constraint trips_driver_id_fkey
    foreign key (driver_id) references public.drivers(id) on delete set null;

update public.trips as t
set plate_no = v.plate_number
from public.vehicles as v
where t.vehicle_id = v.id and t.plate_no is null;

update public.trips as t
set driver_name = d.name
from public.drivers as d
where t.driver_id = d.id and t.driver_name is null;

create index if not exists trips_shipment_date_idx
    on public.trips(shipment_date desc);
