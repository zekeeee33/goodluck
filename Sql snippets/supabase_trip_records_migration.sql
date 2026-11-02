-- Run after supabase_dispatcher_ownership_migration.sql,
-- supabase_fuel_allocation_migration.sql, supabase_truck_trailer_migration.sql,
-- supabase_revenue_dashboard_migration.sql, and
-- supabase_location_dispatch_migration.sql.

alter table public.trips enable row level security;

drop policy if exists trip_records_admin_read on public.trips;
create policy trip_records_admin_read on public.trips
    for select to authenticated
    using (public.dispatch_is_admin());
grant select on public.trips to authenticated;

create or replace function public.admin_trip_records_page(
    p_page integer default 1,
    p_page_size integer default 25,
    p_search text default '',
    p_date_from date default null,
    p_date_to date default null,
    p_origin text default '',
    p_destination text default '',
    p_driver text default '',
    p_load_type text default '',
    p_status text default '',
    p_sort text default 'recorded_at',
    p_sort_dir text default 'desc'
)
returns jsonb
language plpgsql
stable
security definer
set search_path = pg_catalog, public, auth, pg_temp
as $$
declare
    result jsonb;
begin
    if auth.uid() is null or not public.dispatch_is_admin() then
        raise exception 'Only administrators can view trip records';
    end if;
    if p_page is null or p_page < 14
       or p_page_size is null or p_page_size not in (10, 25, 50, 100) then
        raise exception 'Invalid trip records page request';
    end if;
    if p_sort not in ('recorded_at', 'trip_id', 'origin', 'destination', 'driver', 'status', 'rate')
       or p_sort_dir not in ('asc', 'desc') then
        raise exception 'Invalid trip records sort order';
    end if;

    with all_records as (
        select
            trip.id,
            trip.ism_no,
            trip.origin,
            trip.destination,
            coalesce(nullif(trip.driver_name, ''), driver.name) as driver_name,
            trip.driver_id,
            coalesce(nullif(trip.plate_no, ''), truck.plate_number) as truck_plate,
            trailer.plate_number as trailer_plate,
            coalesce(
                movement.load_type,
                case
                    when upper(coalesce(trip.load_details, '')) like 'FULLS%' then 'FULLS'
                    when upper(coalesce(trip.load_details, '')) like 'EMPTIES%' then 'EMPTIES'
                    else null
                end
            ) as load_type,
            coalesce(
                movement.pallet_quantity,
                nullif(substring(trip.load_details from '([0-9]+)[[:space:]]+pallet'), '')::integer
            ) as pallet_quantity,
            trip.time_out,
            trip.time_in,
            movement.departure_at,
            movement.arrival_at,
            coalesce(
                movement.status,
                case
                    when trip.time_in is not null then 'completed'
                    when trip.time_out is not null then 'awaiting_arrival'
                    else 'recorded'
                end
            ) as trip_status,
            trip.truck_route_rate as route_rate,
            trip.revenue_status,
            trip.trip_rate_review_required,
            trip.trailer_review_required,
            coalesce(trip.record_date, trip.shipment_date) as date_recorded,
            trip.shipment_date,
            trip.created_by,
            coalesce(movement.departure_user_id, trip.created_by) as dispatcher_id,
            coalesce(
                nullif(auth_user.raw_user_meta_data ->> 'full_name', ''),
                nullif(auth_user.raw_user_meta_data ->> 'name', ''),
                auth_user.email
            ) as dispatcher_name,
            auth_user.email as dispatcher_email,
            movement.id as movement_id,
            movement.departure_manifest_path is not null as has_departure_manifest,
            movement.arrival_manifest_path is not null as has_arrival_manifest,
            movement.fuel_invoice_path is not null as has_dispatch_fuel_invoice,
            trip.manifest_object_path is not null as has_trip_manifest,
            fuel.invoice_object_path is not null as has_trip_fuel_invoice,
            jsonb_build_object(
                'status', movement.status,
                'departure_at', movement.departure_at,
                'arrival_at', movement.arrival_at,
                'arrival_verified_at', movement.arrival_verified_at,
                'fuel_allocation', movement.fuel_allocation,
                'actual_fuel_expense', movement.actual_fuel_expense,
                'arrival_fuel_expense', movement.arrival_fuel_expense,
                'fuel_remarks', movement.fuel_remarks
            ) as movement_details,
            jsonb_build_object(
                'fuel_allocation', fuel.fuel_allocation,
                'actual_expense', fuel.actual_expense,
                'total_cost', fuel.total_cost,
                'remarks', fuel.remarks
            ) as fuel_details,
            to_jsonb(trip) as trip_details,
            (
                coalesce(trip.trip_rate_review_required, false)
                or coalesce(trip.trailer_review_required, false)
                or movement.status in ('arrival_submitted', 'needs_correction')
            ) as requires_review
        from public.trips as trip
        left join public.drivers as driver on driver.id = trip.driver_id
        left join public.vehicles as truck on truck.id = trip.truck_id
        left join public.trailers as trailer on trailer.id = trip.trailer_id
        left join public.dispatch_movements as movement
            on movement.id = trip.dispatch_movement_id
            or movement.canonical_trip_id = trip.id
        left join public.fuel_logs as fuel on fuel.trip_id = trip.id
        left join auth.users as auth_user
            on auth_user.id = coalesce(movement.departure_user_id, trip.created_by)
    ),
    summary_scope as (
        select *
        from all_records
        where (p_search = '' or
            id::text ilike '%' || p_search || '%'
            or coalesce(ism_no, '') ilike '%' || p_search || '%'
            or coalesce(driver_name, '') ilike '%' || p_search || '%'
            or coalesce(truck_plate, '') ilike '%' || p_search || '%'
            or coalesce(trailer_plate, '') ilike '%' || p_search || '%')
          and (p_date_from is null or date_recorded >= p_date_from)
          and (p_date_to is null or date_recorded <= p_date_to)
          and (p_origin = '' or coalesce(origin, '') ilike '%' || p_origin || '%')
          and (p_destination = '' or coalesce(destination, '') ilike '%' || p_destination || '%')
          and (p_driver = '' or driver_id::text = p_driver
               or coalesce(driver_name, '') = p_driver)
          and (p_load_type = '' or load_type = p_load_type)
    ),
    filtered_records as (
        select *
        from summary_scope
        where p_status = '' or trip_status = p_status
    ),
    page_rows as (
        select ordered.*
        from (
            select filtered_records.*,
                row_number() over (
                    order by
                        case when p_sort = 'trip_id' and p_sort_dir = 'asc' then id end asc,
                        case when p_sort = 'trip_id' and p_sort_dir = 'desc' then id end desc,
                        case when p_sort = 'recorded_at' and p_sort_dir = 'asc' then date_recorded end asc nulls last,
                        case when p_sort = 'recorded_at' and p_sort_dir = 'desc' then date_recorded end desc nulls last,
                        case when p_sort = 'origin' and p_sort_dir = 'asc' then origin end asc,
                        case when p_sort = 'origin' and p_sort_dir = 'desc' then origin end desc,
                        case when p_sort = 'destination' and p_sort_dir = 'asc' then destination end asc,
                        case when p_sort = 'destination' and p_sort_dir = 'desc' then destination end desc,
                        case when p_sort = 'driver' and p_sort_dir = 'asc' then driver_name end asc,
                        case when p_sort = 'driver' and p_sort_dir = 'desc' then driver_name end desc,
                        case when p_sort = 'status' and p_sort_dir = 'asc' then trip_status end asc,
                        case when p_sort = 'status' and p_sort_dir = 'desc' then trip_status end desc,
                        case when p_sort = 'rate' and p_sort_dir = 'asc' then route_rate end asc nulls last,
                        case when p_sort = 'rate' and p_sort_dir = 'desc' then route_rate end desc nulls last,
                        date_recorded desc nulls last,
                        id desc
                ) as page_order
            from filtered_records
        ) as ordered
        where ordered.page_order > (p_page - 1) * p_page_size
          and ordered.page_order <= p_page * p_page_size
    )
    select jsonb_build_object(
        'records', coalesce((
            select jsonb_agg(jsonb_build_object(
                'id', record.id,
                'ism_no', record.ism_no,
                'origin', record.origin,
                'destination', record.destination,
                'driver_id', record.driver_id,
                'driver_name', record.driver_name,
                'truck_plate', record.truck_plate,
                'trailer_plate', record.trailer_plate,
                'load_type', record.load_type,
                'pallet_quantity', record.pallet_quantity,
                'time_out', record.time_out,
                'time_in', record.time_in,
                'departure_at', record.departure_at,
                'arrival_at', record.arrival_at,
                'status', record.trip_status,
                'route_rate', record.route_rate,
                'revenue_status', record.revenue_status,
                'date_recorded', record.date_recorded,
                'dispatcher_name', record.dispatcher_name,
                'dispatcher_email', record.dispatcher_email,
                'movement_id', record.movement_id,
                'has_departure_manifest', record.has_departure_manifest,
                'has_arrival_manifest', record.has_arrival_manifest,
                'has_dispatch_fuel_invoice', record.has_dispatch_fuel_invoice,
                'has_trip_manifest', record.has_trip_manifest,
                'has_trip_fuel_invoice', record.has_trip_fuel_invoice,
                'requires_review', record.requires_review,
                'movement', record.movement_details,
                'fuel', record.fuel_details,
                'details', record.trip_details
            ) order by record.page_order)
            from page_rows as record
        ), '[]'::jsonb),
        'total', (select count(*) from filtered_records),
        'page', p_page,
        'page_size', p_page_size,
        'summary', jsonb_build_object(
            'total_trips', (select count(*) from summary_scope),
            'completed_trips', (select count(*) from summary_scope where trip_status = 'completed'),
            'pending_arrivals', (select count(*) from summary_scope where trip_status in (
                'awaiting_arrival', 'arrival_submitted', 'needs_correction'
            )),
            'trips_requiring_review', (select count(*) from summary_scope where requires_review)
        ),
        'filters', jsonb_build_object(
            'origins', coalesce((
                select jsonb_agg(option_value order by option_value)
                from (select distinct origin as option_value from all_records where nullif(origin, '') is not null) as choices
            ), '[]'::jsonb),
            'destinations', coalesce((
                select jsonb_agg(option_value order by option_value)
                from (select distinct destination as option_value from all_records where nullif(destination, '') is not null) as choices
            ), '[]'::jsonb),
            'drivers', coalesce((
                select jsonb_agg(jsonb_build_object('id', driver_id, 'name', driver_name) order by driver_name)
                from (
                    select distinct driver_id, driver_name
                    from all_records
                    where driver_id is not null and nullif(driver_name, '') is not null
                ) as choices
            ), '[]'::jsonb),
            'statuses', coalesce((
                select jsonb_agg(option_value order by option_value)
                from (select distinct trip_status as option_value from all_records) as choices
            ), '[]'::jsonb)
        )
    ) into result;

    return result;
end;
$$;

revoke all on function public.admin_trip_records_page(
    integer, integer, text, date, date, text, text, text, text, text, text, text
) from public, anon;
grant execute on function public.admin_trip_records_page(
    integer, integer, text, date, date, text, text, text, text, text, text, text
) to authenticated;
