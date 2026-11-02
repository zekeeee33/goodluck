-- Server-filtered trip reports for administrator Trip Records.
-- Apply after supabase_trip_records_migration.sql and
-- supabase_revenue_dashboard_migration.sql.

create or replace function public.admin_trip_report_options()
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
        raise exception 'Only administrators can generate trip reports';
    end if;

    select jsonb_build_object(
        'drivers', coalesce((
            select jsonb_agg(jsonb_build_object('id', driver.id, 'name', driver.name)
                order by driver.name, driver.id)
            from public.drivers as driver
        ), '[]'::jsonb),
        'trucks', coalesce((
            select jsonb_agg(jsonb_build_object('id', vehicle.id, 'plate_number', vehicle.plate_number)
                order by vehicle.plate_number, vehicle.id)
            from public.vehicles as vehicle
        ), '[]'::jsonb),
        'trailers', coalesce((
            select jsonb_agg(jsonb_build_object('id', trailer.id, 'plate_number', trailer.plate_number)
                order by trailer.plate_number, trailer.id)
            from public.trailers as trailer
        ), '[]'::jsonb),
        'origins', coalesce((
            select jsonb_agg(value order by value)
            from (
                select distinct nullif(trim(trip.origin), '') as value
                from public.trips as trip
                where nullif(trim(trip.origin), '') is not null
            ) as choices
        ), '[]'::jsonb),
        'destinations', coalesce((
            select jsonb_agg(value order by value)
            from (
                select distinct nullif(trim(trip.destination), '') as value
                from public.trips as trip
                where nullif(trim(trip.destination), '') is not null
            ) as choices
        ), '[]'::jsonb),
        'routes', coalesce((
            select jsonb_agg(jsonb_build_object('value', value, 'label', label) order by label)
            from (
                select distinct
                    coalesce(trip.route_number::text, nullif(trim(trip.route_pair), ''),
                        nullif(trim(trip.route), '')) as value,
                    coalesce(
                        case when trip.route_number is not null
                            then 'Route ' || trip.route_number::text end,
                        nullif(trim(trip.route_pair), ''),
                        nullif(trim(trip.route), '')
                    ) as label
                from public.trips as trip
                where trip.route_number is not null
                   or nullif(trim(trip.route_pair), '') is not null
                   or nullif(trim(trip.route), '') is not null
            ) as choices
            where value is not null and label is not null
        ), '[]'::jsonb),
        'statuses', '[
            {"value":"completed","label":"Completed"},
            {"value":"awaiting_arrival","label":"Awaiting arrival"},
            {"value":"arrival_submitted","label":"Arrival submitted"},
            {"value":"needs_correction","label":"Needs correction"},
            {"value":"recorded","label":"Recorded"}
        ]'::jsonb
    ) into result;

    return result;
end;
$$;

drop function if exists public.admin_trip_report_page(
    integer, integer, text, date, date, bigint[], bigint[], text[], text[],
    text[], text[], text
);
drop function if exists public.admin_trip_report_page(
    integer, integer, text, date, date, bigint[], bigint[], bigint[],
    text[], text[], text[], text[], text
);

create or replace function public.admin_trip_report_page(
    p_page integer default 1,
    p_page_size integer default 100,
    p_search text default '',
    p_date_from date default null,
    p_date_to date default null,
    p_driver_ids bigint[] default '{}',
    p_truck_ids bigint[] default '{}',
    p_trailer_ids bigint[] default '{}',
    p_origins text[] default '{}',
    p_destinations text[] default '{}',
    p_routes text[] default '{}',
    p_statuses text[] default '{}',
    p_report_type text default 'all'
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
        raise exception 'Only administrators can generate trip reports';
    end if;
    if p_page is null or p_page < 1 or p_page > 100000
       or p_page_size is null or p_page_size not between 1 and 100 then
        raise exception 'Invalid trip report pagination';
    end if;
    if p_date_from is not null and p_date_to is not null
       and p_date_from > p_date_to then
        raise exception 'Start date must be on or before end date';
    end if;
    if p_report_type not in (
        'all', 'driver', 'truck', 'trailer', 'origin', 'destination',
        'route', 'date', 'custom'
    ) then
        raise exception 'Invalid trip report category';
    end if;
    if cardinality(coalesce(p_driver_ids, '{}')) > 100
       or cardinality(coalesce(p_truck_ids, '{}')) > 100
       or cardinality(coalesce(p_trailer_ids, '{}')) > 100
       or cardinality(coalesce(p_origins, '{}')) > 100
       or cardinality(coalesce(p_destinations, '{}')) > 100
       or cardinality(coalesce(p_routes, '{}')) > 100
       or cardinality(coalesce(p_statuses, '{}')) > 100 then
        raise exception 'Too many trip report filter values';
    end if;

    with all_records as (
        select
            trip.id,
            trip.ism_no,
            coalesce(trip.shipment_date, trip.record_date) as trip_date,
            trip.shipment_date,
            coalesce(trip.record_date, trip.shipment_date) as date_recorded,
            trip.time_in,
            trip.time_out,
            trip.origin,
            trip.destination,
            trip.route,
            trip.route_number,
            trip.route_pair,
            coalesce(nullif(trip.driver_name, ''), driver.name) as driver_name,
            trip.driver_id,
            coalesce(trip.truck_id, trip.vehicle_id) as truck_id,
            coalesce(nullif(trip.plate_no, ''), truck.plate_number) as truck_plate,
            trip.trailer_id,
            trailer.plate_number as trailer_plate,
            trip.start_odometer,
            trip.end_odometer,
            case
                when trip.start_odometer is not null
                 and trip.end_odometer is not null
                 and trip.end_odometer >= trip.start_odometer
                then trip.end_odometer - trip.start_odometer
                else null
            end as distance,
            trip.load_details,
            trip.trip_fuel,
            trip.truck_route_rate as route_rate,
            trip.revenue_status,
            coalesce(adjustments.adjustment_total, 0)::numeric(14, 2)
                as adjustment_total,
            (
                trip.revenue_status <> 'cancelled'
                and trip.truck_route_rate is not null
                and trip.truck_route_rate >= 0
                and not coalesce(trip.trip_rate_review_required, true)
                and not coalesce(trip.trailer_review_required, true)
                and trip.pallet_capacity is not null
            ) as is_revenue_eligible,
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
            coalesce(
                movement.status,
                case
                    when trip.time_in is not null then 'completed'
                    when trip.time_out is not null then 'awaiting_arrival'
                    else 'recorded'
                end
            ) as trip_status,
            coalesce(
                nullif(auth_user.raw_user_meta_data ->> 'full_name', ''),
                nullif(auth_user.raw_user_meta_data ->> 'name', ''),
                auth_user.email
            ) as dispatcher_name,
            auth_user.email as dispatcher_email,
            trip.notes
        from public.trips as trip
        left join public.drivers as driver on driver.id = trip.driver_id
        left join public.vehicles as truck
            on truck.id = coalesce(trip.truck_id, trip.vehicle_id)
        left join public.trailers as trailer on trailer.id = trip.trailer_id
        left join lateral (
            select movement_row.*
            from public.dispatch_movements as movement_row
            where movement_row.id = trip.dispatch_movement_id
               or movement_row.canonical_trip_id = trip.id
            order by
                (movement_row.id = trip.dispatch_movement_id) desc,
                movement_row.created_at desc nulls last,
                movement_row.id desc
            limit 1
        ) as movement on true
        left join lateral (
            select sum(adjustment.amount)::numeric(14, 2) as adjustment_total
            from public.revenue_adjustments as adjustment
            where adjustment.trip_id = trip.id
        ) as adjustments on true
        left join auth.users as auth_user
            on auth_user.id = coalesce(movement.departure_user_id, trip.created_by)
    ),
    revenue_ranked_records as (
        select all_records.*,
            row_number() over (
                partition by
                    nullif(trim(ism_no), ''),
                    case when nullif(trim(ism_no), '') is null then id end
                order by is_revenue_eligible desc, shipment_date asc nulls last, id asc
            ) as revenue_rank
        from all_records
    ),
    filtered_records as (
        select revenue_ranked_records.*,
            case
                when revenue_rank = 1 and is_revenue_eligible
                then route_rate + adjustment_total
                else null
            end as trip_revenue
        from revenue_ranked_records
        where (nullif(trim(coalesce(p_search, '')), '') is null
               or coalesce(id::text, '') ilike '%' || trim(p_search) || '%'
               or coalesce(ism_no, '') ilike '%' || trim(p_search) || '%'
               or coalesce(driver_name, '') ilike '%' || trim(p_search) || '%'
               or coalesce(truck_plate, '') ilike '%' || trim(p_search) || '%'
               or coalesce(trailer_plate, '') ilike '%' || trim(p_search) || '%'
               or coalesce(origin, '') ilike '%' || trim(p_search) || '%'
               or coalesce(destination, '') ilike '%' || trim(p_search) || '%')
          and (p_date_from is null or trip_date >= p_date_from)
          and (p_date_to is null or trip_date <= p_date_to)
          and (cardinality(coalesce(p_driver_ids, '{}')) = 0
               or driver_id = any(p_driver_ids))
          and (cardinality(coalesce(p_truck_ids, '{}')) = 0
               or truck_id = any(p_truck_ids))
          and (cardinality(coalesce(p_trailer_ids, '{}')) = 0
               or trailer_id = any(p_trailer_ids))
          and (cardinality(coalesce(p_origins, '{}')) = 0
               or origin = any(p_origins))
          and (cardinality(coalesce(p_destinations, '{}')) = 0
               or destination = any(p_destinations))
          and (cardinality(coalesce(p_routes, '{}')) = 0
               or coalesce(route_number::text, nullif(trim(route_pair), ''),
                    nullif(trim(route), '')) = any(p_routes))
          and (cardinality(coalesce(p_statuses, '{}')) = 0
               or trip_status = any(p_statuses))
    ),
    page_rows as (
        select filtered_records.*,
            row_number() over (
                order by
                    case when p_report_type = 'driver' then driver_name end asc nulls last,
                    case when p_report_type = 'truck' then truck_plate end asc nulls last,
                    case when p_report_type = 'trailer' then trailer_plate end asc nulls last,
                    case when p_report_type = 'origin' then origin end asc nulls last,
                    case when p_report_type = 'destination' then destination end asc nulls last,
                    case when p_report_type = 'route' then
                        coalesce(route_number::text, nullif(trim(route_pair), ''),
                            nullif(trim(route), '')) end asc nulls last,
                    case when p_report_type = 'date' then trip_date end asc nulls last,
                    trip_date desc nulls last,
                    id desc
            ) as row_order
        from filtered_records
    )
    select jsonb_build_object(
        'records', coalesce((
            select jsonb_agg(jsonb_build_object(
                'id', record.id,
                'ism_no', record.ism_no,
                'trip_date', record.trip_date,
                'shipment_date', record.shipment_date,
                'date_recorded', record.date_recorded,
                'time_in', record.time_in,
                'time_out', record.time_out,
                'origin', record.origin,
                'destination', record.destination,
                'route', record.route,
                'route_number', record.route_number,
                'route_pair', record.route_pair,
                'driver_id', record.driver_id,
                'driver_name', record.driver_name,
                'truck_id', record.truck_id,
                'truck_plate', record.truck_plate,
                'trailer_id', record.trailer_id,
                'trailer_plate', record.trailer_plate,
                'trip_fuel', record.trip_fuel,
                'start_odometer', record.start_odometer,
                'end_odometer', record.end_odometer,
                'distance', record.distance,
                'load_type', record.load_type,
                'pallet_quantity', record.pallet_quantity,
                'load_details', record.load_details,
                'route_rate', record.route_rate,
                'trip_revenue', record.trip_revenue,
                'revenue_status', record.revenue_status,
                'status', record.trip_status,
                'dispatcher_name', record.dispatcher_name,
                'dispatcher_email', record.dispatcher_email,
                'notes', record.notes
            ) order by record.row_order)
            from page_rows as record
            where record.row_order > (p_page - 1) * p_page_size
              and record.row_order <= p_page * p_page_size
        ), '[]'::jsonb),
        'page', p_page,
        'page_size', p_page_size,
        'total', (select count(*) from filtered_records),
        'summary', jsonb_build_object(
            'total_trips', (select count(*) from filtered_records),
            'total_distance', (select sum(distance) from filtered_records),
            'distance_trip_count', (select count(distance) from filtered_records),
            'total_revenue', (select sum(trip_revenue) from filtered_records),
            'revenue_trip_count', (select count(trip_revenue) from filtered_records),
            'average_revenue_per_trip', (
                select avg(trip_revenue) from filtered_records
            )
        )
    ) into result;

    return result;
end;
$$;

revoke all on function public.admin_trip_report_options() from public, anon;
revoke all on function public.admin_trip_report_page(
    integer, integer, text, date, date, bigint[], bigint[], bigint[],
    text[], text[], text[], text[], text
) from public, anon;
grant execute on function public.admin_trip_report_options() to authenticated;
grant execute on function public.admin_trip_report_page(
    integer, integer, text, date, date, bigint[], bigint[], bigint[],
    text[], text[], text[], text[], text
) to authenticated;
