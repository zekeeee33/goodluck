-- Automatically register the official trip when a validated departure is saved.
-- Run after supabase_location_dispatch_migration.sql and the dispatch load
-- catalog/no-load migrations.

begin;

alter table public.dispatch_movements
    add column if not exists trip_date date;

update public.dispatch_movements
set trip_date = (departure_at at time zone 'Asia/Manila')::date
where trip_date is null
  and departure_at is not null;

alter table public.dispatch_movements
    alter column trip_date set not null,
    alter column departure_at drop not null,
    drop constraint if exists dispatch_movements_arrival_pair;

comment on column public.dispatch_movements.trip_date is
    'Explicit local trip date; independent of optional departure and arrival timestamps.';

create or replace function public.register_dispatch_movement_trip(p_movement_id uuid)
returns bigint
language plpgsql
security definer
set search_path = pg_catalog, public, auth, pg_temp
as $$
declare
    movement public.dispatch_movements%rowtype;
    route_row public.truck_routes%rowtype;
    rate_row public.truck_route_rates%rowtype;
    driver_name text;
    truck_plate text;
    trailer_capacity integer;
    created_trip_id bigint;
    has_rate boolean := false;
begin
    if auth.uid() is null then
        raise exception 'Authentication required';
    end if;

    select * into movement
    from public.dispatch_movements
    where id = p_movement_id
    for update;
    if not found then
        raise exception 'Movement not found';
    end if;
    if movement.canonical_trip_id is not null then
        return movement.canonical_trip_id;
    end if;
    if movement.departure_user_id <> auth.uid()
       and not public.dispatch_is_admin() then
        raise exception 'You are not authorized to register this movement';
    end if;

    select * into route_row
    from public.truck_routes
    where origin_code = movement.origin_location_id
      and destination_code = movement.destination_location_id
      and active;
    if not found then
        raise exception 'No active route is configured for this movement';
    end if;

    select name into driver_name
    from public.drivers
    where id = movement.driver_id;
    select plate_number into truck_plate
    from public.vehicles
    where id = movement.truck_id;
    select pallet_capacity into trailer_capacity
    from public.trailers
    where id = movement.trailer_id;

    select * into rate_row
    from public.truck_route_rates
    where route_id = route_row.id
      and pallet_capacity = trailer_capacity
      and active
      and hauling_rate is not null
    limit 1;
    has_rate := found;

    insert into public.trips (
        vehicle_id, truck_id, trailer_id, driver_id, driver_name, plate_no,
        route, start_odometer, end_odometer, trip_date, shipment_date, ism_no,
        time_out, time_in, origin, destination, route_id, route_number,
        route_pair, pallet_capacity, truck_route_rate_id, truck_route_rate,
        trip_rate_review_required, trailer_review_required, load_details,
        dispatch_movement_id, created_by, manifest_object_path
    ) values (
        movement.truck_id, movement.truck_id, movement.trailer_id,
        movement.driver_id, driver_name, truck_plate,
        route_row.origin_name || ' to ' || route_row.destination_name, 0, 0,
        movement.trip_date, movement.trip_date, movement.ism_no,
        case when movement.departure_at is null then null
             else (movement.departure_at at time zone 'Asia/Manila')::time end,
        null, route_row.origin_name, route_row.destination_name,
        route_row.id, route_row.route_number, route_row.route_pair,
        trailer_capacity,
        case when has_rate then rate_row.id else null end,
        case when has_rate then rate_row.hauling_rate else null end,
        not has_rate, false,
        movement.load_type || ' — ' || movement.pallet_quantity || ' pallets',
        movement.id, movement.departure_user_id, movement.departure_manifest_path
    ) returning id into created_trip_id;

    update public.dispatch_movements
    set canonical_trip_id = created_trip_id,
        updated_at = now()
    where id = movement.id;

    if movement.fuel_allocation is not null
       or movement.actual_fuel_expense is not null
       or movement.fuel_remarks is not null then
        insert into public.fuel_logs (
            vehicle_id, trip_id, fuel_type, quantity, total_cost,
            actual_expense, invoice_object_path, remarks, logged_on, created_by
        ) values (
            movement.truck_id, created_trip_id, 'diesel',
            movement.fuel_allocation,
            coalesce(movement.actual_fuel_expense, 0),
            coalesce(movement.actual_fuel_expense, 0),
            movement.fuel_invoice_path, movement.fuel_remarks,
            movement.trip_date, movement.departure_user_id
        )
        on conflict (trip_id) where trip_id is not null do nothing;
    end if;

    perform public.dispatch_log_event(
        p_movement_id,
        'official_trip_registered',
        jsonb_build_object('canonical_trip_id', created_trip_id)
    );
    return created_trip_id;
end;
$$;

create or replace function public.create_dispatch_movement(
    p_origin_location_id text,
    p_destination_location_id text,
    p_ism_no text,
    p_truck_id bigint,
    p_driver_id bigint,
    p_trailer_id bigint,
    p_load_type text,
    p_pallet_quantity integer,
    p_departure_at timestamptz,
    p_fuel_allocation numeric,
    p_actual_fuel_expense numeric,
    p_fuel_remarks text,
    p_trip_date date
)
returns uuid
language plpgsql
security definer
set search_path = pg_catalog, public, auth, pg_temp
as $$
declare
    movement_id uuid;
    existing_movement public.dispatch_movements%rowtype;
    trailer_capacity integer;
begin
    if auth.uid() is null then
        raise exception 'Authentication required';
    end if;
    if not public.dispatch_has_location(p_origin_location_id, 'depart') then
        raise exception 'You are not authorized to depart from this location';
    end if;
    if p_origin_location_id = p_destination_location_id then
        raise exception 'Origin and destination must be different';
    end if;
    if (
        select count(*)
        from public.dispatch_locations
        where id in (p_origin_location_id, p_destination_location_id)
          and active
    ) <> 2 then
        raise exception 'Origin and destination must be active locations';
    end if;
    if not exists (
        select 1 from public.truck_routes as route
        where route.origin_code = p_origin_location_id
          and route.destination_code = p_destination_location_id
          and route.active
    ) then
        raise exception 'The selected route is not configured';
    end if;
    if nullif(trim(p_ism_no), '') is null
       or p_trip_date is null
       or p_load_type is null
       or p_load_type not in ('FULLS', 'EMPTIES', 'NO_LOAD')
       or p_pallet_quantity is null
       or (p_load_type = 'NO_LOAD' and p_pallet_quantity <> 0)
       or (p_load_type <> 'NO_LOAD' and p_pallet_quantity < 1) then
        raise exception 'Complete all required departure fields';
    end if;
    if not exists (
        select 1 from public.vehicles
        where id = p_truck_id and status in ('active', 'available', 'assigned')
    ) then
        raise exception 'Select an active truck';
    end if;
    if not exists (
        select 1 from public.drivers
        where id = p_driver_id and status = 'active'
    ) then
        raise exception 'Select an active driver';
    end if;
    select pallet_capacity into trailer_capacity
    from public.trailers
    where id = p_trailer_id and status = 'active';
    if not found then
        raise exception 'Select an active trailer';
    end if;
    if trailer_capacity is null then
        raise exception 'Trailer pallet capacity must be configured before departure';
    end if;
    if p_pallet_quantity > trailer_capacity then
        raise exception 'Pallet quantity exceeds trailer capacity';
    end if;

    select * into existing_movement
    from public.dispatch_movements
    where lower(trim(ism_no)) = lower(trim(p_ism_no))
    for update;
    if found then
        if existing_movement.departure_user_id = auth.uid()
           and existing_movement.origin_location_id = p_origin_location_id
           and existing_movement.destination_location_id = p_destination_location_id
           and existing_movement.truck_id = p_truck_id
           and existing_movement.driver_id = p_driver_id
           and existing_movement.trailer_id = p_trailer_id
           and existing_movement.load_type = p_load_type
           and existing_movement.pallet_quantity = p_pallet_quantity
           and existing_movement.departure_at is not distinct from p_departure_at
           and existing_movement.fuel_allocation is not distinct from p_fuel_allocation
           and existing_movement.actual_fuel_expense is not distinct from p_actual_fuel_expense
           and existing_movement.fuel_remarks is not distinct from nullif(trim(p_fuel_remarks), '')
           and existing_movement.trip_date = p_trip_date then
            return existing_movement.id;
        end if;
        raise exception 'This ISM number is already assigned to a movement';
    end if;

    insert into public.dispatch_movements (
        origin_location_id, destination_location_id, ism_no, truck_id, driver_id,
        trailer_id, load_type, pallet_quantity, departure_at, trip_date,
        departure_user_id, fuel_allocation, actual_fuel_expense, fuel_remarks
    ) values (
        p_origin_location_id, p_destination_location_id, trim(p_ism_no),
        p_truck_id, p_driver_id, p_trailer_id, p_load_type, p_pallet_quantity,
        p_departure_at, p_trip_date, auth.uid(), p_fuel_allocation,
        p_actual_fuel_expense, nullif(trim(p_fuel_remarks), '')
    ) returning id into movement_id;

    perform public.dispatch_log_event(
        movement_id,
        'departure_created',
        jsonb_build_object(
            'origin_location_id', p_origin_location_id,
            'destination_location_id', p_destination_location_id,
            'trip_date', p_trip_date,
            'departure_at', p_departure_at,
            'truck_id', p_truck_id,
            'driver_id', p_driver_id,
            'trailer_id', p_trailer_id,
            'load_type', p_load_type,
            'pallet_quantity', p_pallet_quantity
        )
    );
    return movement_id;
end;
$$;

create or replace function public.create_dispatch_movement_with_load(
    p_origin_location_id text,
    p_destination_location_id text,
    p_ism_no text,
    p_truck_id bigint,
    p_driver_id bigint,
    p_trailer_id bigint,
    p_load_type text,
    p_pallet_quantity integer,
    p_departure_at timestamptz,
    p_fuel_allocation numeric,
    p_actual_fuel_expense numeric,
    p_fuel_remarks text,
    p_load_items jsonb,
    p_trip_date date
)
returns uuid
language plpgsql
security definer
set search_path = pg_catalog, public, auth, pg_temp
as $$
declare
    movement_id uuid;
    normalized_items jsonb;
    requested_count integer;
    matched_count integer;
    existing_load_items jsonb;
    existing_trip_id bigint;
begin
    if auth.uid() is null then
        raise exception 'Authentication required';
    end if;
    if p_load_items is null or jsonb_typeof(p_load_items) <> 'array'
       or jsonb_array_length(p_load_items) > 100 then
        raise exception 'Select valid load items';
    end if;
    if p_load_type = 'FULLS' and jsonb_array_length(p_load_items) = 0 then
        raise exception 'Add at least one product to the load';
    end if;
    if p_load_type in ('EMPTIES', 'NO_LOAD')
       and jsonb_array_length(p_load_items) > 0 then
        raise exception 'Remove products from a movement without catalog items';
    end if;
    if exists (
        select 1
        from jsonb_array_elements(p_load_items) as item(value)
        where jsonb_typeof(item.value) <> 'object'
           or coalesce(item.value ->> 'product_id', '') !~ '^[1-9][0-9]*$'
           or coalesce(item.value ->> 'pallet_quantity', '') !~ '^[1-9][0-9]*$'
    ) then
        raise exception 'Each load item needs a valid product and pallet quantity';
    end if;

    select count(*)::integer,
        count(distinct item.value ->> 'product_id')::integer
    into requested_count, matched_count
    from jsonb_array_elements(p_load_items) as item(value);
    if requested_count <> matched_count then
        raise exception 'A product can only be listed once in the load';
    end if;
    select count(*)::integer
    into matched_count
    from jsonb_array_elements(p_load_items) as item(value)
    join public.load_catalog as product
      on product.id = (item.value ->> 'product_id')::bigint
     and product.is_active;
    if requested_count <> matched_count then
        raise exception 'A selected load product is unavailable';
    end if;

    select coalesce(
        jsonb_agg(
            jsonb_build_object(
                'product_id', product.id,
                'section', product.section,
                'brand', product.brand,
                'packing', product.packing,
                'pack_quantity', product.quantity,
                'pallet_quantity', (item.value ->> 'pallet_quantity')::integer
            )
            order by product.section, product.brand, product.packing, product.id
        ),
        '[]'::jsonb
    )
    into normalized_items
    from jsonb_array_elements(p_load_items) as item(value)
    join public.load_catalog as product
      on product.id = (item.value ->> 'product_id')::bigint
     and product.is_active;

    movement_id := public.create_dispatch_movement(
        p_origin_location_id, p_destination_location_id, p_ism_no, p_truck_id,
        p_driver_id, p_trailer_id, p_load_type, p_pallet_quantity,
        p_departure_at, p_fuel_allocation, p_actual_fuel_expense,
        p_fuel_remarks, p_trip_date
    );

    select load_items, canonical_trip_id
    into existing_load_items, existing_trip_id
    from public.dispatch_movements
    where id = movement_id
    for update;
    if existing_trip_id is not null then
        if existing_load_items is distinct from normalized_items then
            raise exception 'This ISM number is already registered with different load details';
        end if;
    else
        update public.dispatch_movements
        set load_items = normalized_items,
            updated_at = now()
        where id = movement_id;
    end if;

    if jsonb_array_length(normalized_items) > 0 then
        perform public.dispatch_log_event(
            movement_id,
            'load_items_recorded',
            jsonb_build_object('items', normalized_items)
        );
    end if;
    perform public.register_dispatch_movement_trip(movement_id);
    return movement_id;
end;
$$;

create or replace function public.submit_dispatch_arrival(
    p_movement_id uuid,
    p_arrival_at timestamptz,
    p_arrival_fuel_expense numeric default null
)
returns void
language plpgsql
security definer
set search_path = pg_catalog, public, auth, pg_temp
as $$
declare
    movement public.dispatch_movements%rowtype;
    total_fuel_expense numeric(12, 2);
begin
    select * into movement
    from public.dispatch_movements
    where id = p_movement_id
    for update;
    if not found then
        raise exception 'Movement not found';
    end if;
    if movement.status = 'completed'
       and movement.canonical_trip_id is not null
       and movement.arrival_user_id = auth.uid() then
        return;
    end if;
    if not public.dispatch_has_location(movement.destination_location_id, 'arrive')
       or movement.arrival_verified_by <> auth.uid()
       or movement.arrival_verified_at is null
       or movement.status not in ('awaiting_arrival', 'needs_correction') then
        raise exception 'Verify the ISM before submitting arrival';
    end if;
    if movement.departure_manifest_path is null
       or movement.arrival_manifest_path is null then
        raise exception 'Departure and arrival manifests are required';
    end if;
    if p_arrival_at is not null
       and movement.departure_at is not null
       and p_arrival_at < movement.departure_at then
        raise exception 'Arrival time cannot be earlier than departure time';
    end if;
    if movement.canonical_trip_id is null then
        perform public.register_dispatch_movement_trip(p_movement_id);
        select * into movement
        from public.dispatch_movements
        where id = p_movement_id
        for update;
    end if;

    update public.dispatch_movements
    set arrival_at = p_arrival_at,
        arrival_user_id = auth.uid(),
        arrival_fuel_expense = p_arrival_fuel_expense,
        status = 'completed',
        finalized_at = now(),
        finalized_by = auth.uid(),
        updated_at = now()
    where id = p_movement_id;

    update public.trips
    set time_in = case when p_arrival_at is null then null
                       else (p_arrival_at at time zone 'Asia/Manila')::time end
    where id = movement.canonical_trip_id;

    total_fuel_expense :=
        coalesce(movement.actual_fuel_expense, 0)
        + coalesce(p_arrival_fuel_expense, 0);
    if movement.fuel_allocation is not null
       or movement.actual_fuel_expense is not null
       or p_arrival_fuel_expense is not null
       or movement.fuel_remarks is not null
       or movement.fuel_invoice_path is not null then
        insert into public.fuel_logs (
            vehicle_id, trip_id, fuel_type, quantity, total_cost,
            actual_expense, invoice_object_path, remarks, logged_on, created_by
        ) values (
            movement.truck_id, movement.canonical_trip_id, 'diesel',
            movement.fuel_allocation, total_fuel_expense, total_fuel_expense,
            movement.fuel_invoice_path, movement.fuel_remarks,
            movement.trip_date, movement.departure_user_id
        )
        on conflict (trip_id) where trip_id is not null do update set
            quantity = excluded.quantity,
            total_cost = excluded.total_cost,
            actual_expense = excluded.actual_expense,
            invoice_object_path = coalesce(
                excluded.invoice_object_path, public.fuel_logs.invoice_object_path
            ),
            remarks = excluded.remarks;
    end if;

    perform public.dispatch_log_event(
        p_movement_id,
        'arrival_registered',
        jsonb_build_object(
            'canonical_trip_id', movement.canonical_trip_id,
            'arrival_at', p_arrival_at
        )
    );
end;
$$;

create or replace function public.list_dispatch_movements_page_with_load_items(
    p_queue text,
    p_page integer default 1,
    p_page_size integer default 25,
    p_search text default null
)
returns jsonb
language plpgsql
stable
security definer
set search_path = pg_catalog, public, auth, pg_temp
as $$
declare
    result jsonb;
    movement_rows jsonb;
begin
    if auth.uid() is null then
        raise exception 'Authentication required';
    end if;
    result := public.list_dispatch_movements_page(
        p_queue, p_page, p_page_size, p_search
    );
    select coalesce(
        jsonb_agg(
            movement_row.value || jsonb_build_object(
                'trip_date', movement.trip_date,
                'load_items', coalesce(movement.load_items, '[]'::jsonb)
            )
            order by movement_row.ordinality
        ),
        '[]'::jsonb
    )
    into movement_rows
    from jsonb_array_elements(result -> 'movements')
        with ordinality as movement_row(value, ordinality)
    left join public.dispatch_movements as movement
      on movement.id = (movement_row.value ->> 'id')::uuid;

    return jsonb_set(result, '{movements}', movement_rows, true);
end;
$$;

create or replace function public.sync_dispatch_trip_documents()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog, public
as $$
begin
    if new.canonical_trip_id is not null
       and new.departure_manifest_path is distinct from old.departure_manifest_path then
        update public.trips
        set manifest_object_path = new.departure_manifest_path
        where id = new.canonical_trip_id;
    end if;
    if new.canonical_trip_id is not null
       and new.fuel_invoice_path is distinct from old.fuel_invoice_path then
        update public.fuel_logs
        set invoice_object_path = new.fuel_invoice_path
        where trip_id = new.canonical_trip_id;
    end if;
    return new;
end;
$$;

drop trigger if exists dispatch_trip_documents_sync on public.dispatch_movements;
create trigger dispatch_trip_documents_sync
after update of departure_manifest_path, fuel_invoice_path
on public.dispatch_movements
for each row execute function public.sync_dispatch_trip_documents();

revoke all on function public.register_dispatch_movement_trip(uuid) from public, anon, authenticated;
revoke all on function public.create_dispatch_movement(
    text, text, text, bigint, bigint, bigint, text, integer, timestamptz,
    numeric, numeric, text
) from public, anon, authenticated;
revoke all on function public.create_dispatch_movement_with_load(
    text, text, text, bigint, bigint, bigint, text, integer, timestamptz,
    numeric, numeric, text, jsonb
) from public, anon, authenticated;
revoke all on function public.finalize_dispatch_movement(uuid) from public, anon, authenticated;
revoke all on function public.create_dispatch_movement(
    text, text, text, bigint, bigint, bigint, text, integer, timestamptz,
    numeric, numeric, text, date
) from public, anon;
revoke all on function public.create_dispatch_movement_with_load(
    text, text, text, bigint, bigint, bigint, text, integer, timestamptz,
    numeric, numeric, text, jsonb, date
) from public, anon;
revoke all on function public.submit_dispatch_arrival(uuid, timestamptz, numeric)
    from public, anon;
revoke all on function public.list_dispatch_movements_page_with_load_items(
    text, integer, integer, text
) from public, anon;

grant execute on function public.create_dispatch_movement_with_load(
    text, text, text, bigint, bigint, bigint, text, integer, timestamptz,
    numeric, numeric, text, jsonb, date
) to authenticated;
grant execute on function public.submit_dispatch_arrival(uuid, timestamptz, numeric)
    to authenticated;
grant execute on function public.list_dispatch_movements_page_with_load_items(
    text, integer, integer, text
) to authenticated;

commit;
