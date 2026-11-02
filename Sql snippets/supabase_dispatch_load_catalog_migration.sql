-- Connect the imported beverage catalog to dispatcher movement creation.
-- Run after supabase_load_catalog_import.sql and the location dispatch migration.

begin;

alter table public.dispatch_movements
    add column if not exists load_items jsonb not null default '[]'::jsonb;

comment on column public.dispatch_movements.load_items is
    'Selected products with product_id and per-product pallet_quantity; pack metadata is catalog reference data.';

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'dispatch_movements_load_items_array'
          and conrelid = 'public.dispatch_movements'::regclass
    ) then
        alter table public.dispatch_movements
            add constraint dispatch_movements_load_items_array
            check (jsonb_typeof(load_items) = 'array');
    end if;
end;
$$;

alter table public.load_catalog enable row level security;
revoke all on public.load_catalog from anon, authenticated;

create or replace function public.list_dispatch_load_catalog()
returns jsonb
language plpgsql
stable
security definer
set search_path = pg_catalog, public, auth, pg_temp
as $$
declare
    products jsonb;
begin
    if auth.uid() is null then raise exception 'Authentication required'; end if;
    select coalesce(
        jsonb_agg(
            jsonb_build_object(
                'id', product.id,
                'section', product.section,
                'brand', product.brand,
                'packing', product.packing,
                'quantity', product.quantity
            )
            order by product.section, product.brand, product.packing, product.id
        ),
        '[]'::jsonb
    )
    into products
    from public.load_catalog as product
    where product.is_active;
    return products;
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
    if p_load_type = 'EMPTIES' and jsonb_array_length(p_load_items) > 0 then
        raise exception 'Remove products from an empty-trailer load';
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
    if auth.uid() is null then raise exception 'Authentication required'; end if;
    result := public.list_dispatch_movements_page(
        p_queue, p_page, p_page_size, p_search
    );
    select coalesce(
        jsonb_agg(
            movement_row.value || jsonb_build_object(
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

revoke all on function public.list_dispatch_load_catalog() from public, anon;
revoke all on function public.create_dispatch_movement_with_load(
    text, text, text, bigint, bigint, bigint, text, integer, timestamptz,
    numeric, numeric, text, jsonb
) from public, anon;
revoke all on function public.list_dispatch_movements_page_with_load_items(
    text, integer, integer, text
) from public, anon;

grant execute on function public.list_dispatch_load_catalog() to authenticated;
grant execute on function public.create_dispatch_movement_with_load(
    text, text, text, bigint, bigint, bigint, text, integer, timestamptz,
    numeric, numeric, text, jsonb
) to authenticated;
grant execute on function public.list_dispatch_movements_page_with_load_items(
    text, integer, integer, text
) to authenticated;

commit;
