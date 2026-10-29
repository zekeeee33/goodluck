-- Add support for movements that depart with no load.
-- Run after supabase_dispatch_load_catalog_migration.sql.

begin;

alter table public.dispatch_movements
    drop constraint if exists dispatch_movements_load_type_check,
    drop constraint if exists dispatch_movements_pallet_quantity_check,
    drop constraint if exists dispatch_movements_load_quantity_check;

alter table public.dispatch_movements
    add constraint dispatch_movements_load_type_check
        check (load_type in ('FULLS', 'EMPTIES', 'NO_LOAD')),
    add constraint dispatch_movements_load_quantity_check
        check (
            (load_type = 'NO_LOAD' and pallet_quantity = 0)
            or (load_type <> 'NO_LOAD' and pallet_quantity > 0)
        );

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
    p_fuel_allocation numeric default null,
    p_actual_fuel_expense numeric default null,
    p_fuel_remarks text default null
)
returns uuid
language plpgsql
security definer
set search_path = pg_catalog, public, auth, pg_temp
as $$
declare
    movement_id uuid;
    trailer_capacity integer;
begin
    if auth.uid() is null then raise exception 'Authentication required'; end if;
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
       or p_departure_at is null
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
    ) then raise exception 'Select an active truck'; end if;
    if not exists (
        select 1 from public.drivers where id = p_driver_id and status = 'active'
    ) then raise exception 'Select an active driver'; end if;
    select pallet_capacity into trailer_capacity
    from public.trailers
    where id = p_trailer_id and status = 'active';
    if not found then raise exception 'Select an active trailer'; end if;
    if trailer_capacity is null then
        raise exception 'Trailer pallet capacity must be configured before departure';
    end if;
    if p_pallet_quantity > trailer_capacity then
        raise exception 'Pallet quantity exceeds trailer capacity';
    end if;

    insert into public.dispatch_movements (
        origin_location_id, destination_location_id, ism_no, truck_id, driver_id,
        trailer_id, load_type, pallet_quantity, departure_at, departure_user_id,
        fuel_allocation, actual_fuel_expense, fuel_remarks
    ) values (
        p_origin_location_id, p_destination_location_id, trim(p_ism_no), p_truck_id,
        p_driver_id, p_trailer_id, p_load_type, p_pallet_quantity, p_departure_at,
        auth.uid(), p_fuel_allocation, p_actual_fuel_expense, nullif(trim(p_fuel_remarks), '')
    ) returning id into movement_id;

    perform public.dispatch_log_event(movement_id, 'departure_created',
        jsonb_build_object(
            'origin_location_id', p_origin_location_id,
            'destination_location_id', p_destination_location_id,
            'truck_id', p_truck_id,
            'driver_id', p_driver_id,
            'trailer_id', p_trailer_id,
            'load_type', p_load_type,
            'pallet_quantity', p_pallet_quantity
        ));
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
    p_load_items jsonb
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
begin
    if auth.uid() is null then raise exception 'Authentication required'; end if;
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
        p_origin_location_id,
        p_destination_location_id,
        p_ism_no,
        p_truck_id,
        p_driver_id,
        p_trailer_id,
        p_load_type,
        p_pallet_quantity,
        p_departure_at,
        p_fuel_allocation,
        p_actual_fuel_expense,
        p_fuel_remarks
    );

    update public.dispatch_movements
    set load_items = normalized_items
    where id = movement_id;

    if jsonb_array_length(normalized_items) > 0 then
        perform public.dispatch_log_event(
            movement_id,
            'load_items_recorded',
            jsonb_build_object('items', normalized_items)
        );
    end if;

    return movement_id;
end;
$$;

revoke all on function public.create_dispatch_movement(
    text, text, text, bigint, bigint, bigint, text, integer, timestamptz,
    numeric, numeric, text
) from public, anon;
revoke all on function public.create_dispatch_movement_with_load(
    text, text, text, bigint, bigint, bigint, text, integer, timestamptz,
    numeric, numeric, text, jsonb
) from public, anon;

grant execute on function public.create_dispatch_movement(
    text, text, text, bigint, bigint, bigint, text, integer, timestamptz,
    numeric, numeric, text
) to authenticated;
grant execute on function public.create_dispatch_movement_with_load(
    text, text, text, bigint, bigint, bigint, text, integer, timestamptz,
    numeric, numeric, text, jsonb
) to authenticated;

commit;
