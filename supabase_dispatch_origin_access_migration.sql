-- Let dispatchers choose any active origin while keeping arrival access scoped
-- to location assignments. Creators can still see their own dispatch records.
-- Apply after supabase_location_dispatch_migration.sql.

begin;

create or replace function public.dispatch_has_location(
    p_location_id text,
    p_permission text
)
returns boolean
language sql
stable
security definer
set search_path = pg_catalog, public, auth, pg_temp
as $$
    select public.dispatch_is_admin()
        or (
            p_permission = 'depart'
            and exists (
                select 1
                from public.dispatch_locations as location
                where location.id = p_location_id
                  and location.active
            )
            and exists (
                select 1
                from public.dispatcher_location_assignments as assignment
                join public.dispatch_locations as assigned_location
                  on assigned_location.id = assignment.location_id
                 and assigned_location.active
                where assignment.user_id = auth.uid()
                  and assignment.can_depart
            )
        )
        or exists (
            select 1
            from public.dispatcher_location_assignments as assignment
            join public.dispatch_locations as location
              on location.id = assignment.location_id and location.active
            where assignment.user_id = auth.uid()
              and assignment.location_id = p_location_id
              and (
                  (p_permission = 'arrive' and assignment.can_arrive)
                  or (
                      p_permission = 'view'
                      and (assignment.can_depart or assignment.can_arrive)
                  )
              )
        );
$$;

create or replace function public.list_dispatch_movements()
returns table (
    id uuid,
    origin_location_id text,
    origin_location_name text,
    destination_location_id text,
    destination_location_name text,
    ism_no text,
    truck_id bigint,
    truck_plate text,
    driver_id bigint,
    driver_name text,
    trailer_id bigint,
    trailer_plate text,
    load_type text,
    pallet_quantity integer,
    departure_at timestamptz,
    departure_user_id uuid,
    departure_manifest_path text,
    departure_document_ready boolean,
    fuel_invoice_path text,
    arrival_verified_at timestamptz,
    arrival_at timestamptz,
    arrival_user_id uuid,
    arrival_manifest_path text,
    arrival_fuel_expense numeric,
    status text,
    canonical_trip_id bigint,
    finalized_at timestamptz,
    finalized_by uuid
)
language plpgsql
stable
security definer
set search_path = pg_catalog, public, auth, pg_temp
as $$
begin
    if auth.uid() is null then
        raise exception 'Authentication required';
    end if;
    return query
    select movement.id,
        movement.origin_location_id,
        origin.name,
        movement.destination_location_id,
        destination.name,
        case
            when public.dispatch_is_admin()
              or movement.status = 'completed'
              or movement.departure_user_id = auth.uid()
              or movement.arrival_verified_by = auth.uid()
            then movement.ism_no
            else null
        end,
        movement.truck_id, truck.plate_number, movement.driver_id, driver.name,
        movement.trailer_id, trailer.plate_number, movement.load_type,
        movement.pallet_quantity, movement.departure_at, movement.departure_user_id,
        case
            when public.dispatch_is_admin()
              or movement.departure_user_id = auth.uid()
              or movement.arrival_verified_by = auth.uid()
            then movement.departure_manifest_path
            else null
        end,
        movement.departure_manifest_path is not null,
        case
            when public.dispatch_is_admin()
              or movement.departure_user_id = auth.uid()
              or movement.arrival_verified_by = auth.uid()
            then movement.fuel_invoice_path
            else null
        end,
        movement.arrival_verified_at,
        case
            when public.dispatch_is_admin()
              or public.dispatch_has_location(movement.origin_location_id, 'view')
              or movement.arrival_verified_by = auth.uid()
            then movement.arrival_at
            else null
        end,
        case
            when public.dispatch_is_admin()
              or public.dispatch_has_location(movement.origin_location_id, 'view')
              or movement.arrival_verified_by = auth.uid()
            then movement.arrival_user_id
            else null
        end,
        case
            when public.dispatch_is_admin()
              or public.dispatch_has_location(movement.origin_location_id, 'view')
              or movement.arrival_verified_by = auth.uid()
            then movement.arrival_manifest_path
            else null
        end,
        case
            when public.dispatch_is_admin()
              or public.dispatch_has_location(movement.origin_location_id, 'view')
              or movement.arrival_verified_by = auth.uid()
            then movement.arrival_fuel_expense
            else null
        end,
        movement.status, movement.canonical_trip_id,
        movement.finalized_at, movement.finalized_by
    from public.dispatch_movements as movement
    join public.dispatch_locations as origin on origin.id = movement.origin_location_id
    join public.dispatch_locations as destination on destination.id = movement.destination_location_id
    left join public.vehicles as truck on truck.id = movement.truck_id
    left join public.drivers as driver on driver.id = movement.driver_id
    left join public.trailers as trailer on trailer.id = movement.trailer_id
    where public.dispatch_is_admin()
       or public.dispatch_has_location(movement.origin_location_id, 'view')
       or (
           movement.status <> 'completed'
           and public.dispatch_has_location(movement.origin_location_id, 'depart')
       )
       or movement.departure_user_id = auth.uid()
       or (
           movement.departure_manifest_path is not null
           and public.dispatch_has_location(movement.destination_location_id, 'view')
       )
    order by movement.created_at desc;
end;
$$;

create or replace function public.list_dispatch_movements_page(
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
    total_count bigint;
    page_rows jsonb;
    search_text text := lower(trim(coalesce(p_search, '')));
begin
    if auth.uid() is null then raise exception 'Authentication required'; end if;
    if p_queue is null or p_queue not in ('departures', 'arrivals', 'completed')
       or p_page is null or p_page_size is null
       or p_page < 1 or p_page > 100000
       or p_page_size < 1 or p_page_size > 100
       or length(search_text) > 120 then
        raise exception 'Invalid movement page request';
    end if;

    with eligible as materialized (
        select movement.*
        from public.list_dispatch_movements() as movement
        where (
            (
                p_queue = 'departures'
                and movement.status <> 'completed'
                and public.dispatch_has_location(movement.origin_location_id, 'depart')
            )
            or (
                p_queue = 'arrivals'
                and movement.status <> 'completed'
                and movement.departure_document_ready
                and public.dispatch_has_location(movement.destination_location_id, 'arrive')
            )
            or (
                p_queue = 'completed'
                and movement.status = 'completed'
            )
        )
        and (
            search_text = ''
            or coalesce(movement.ism_no, '') ilike '%' || search_text || '%'
            or coalesce(movement.origin_location_id, '') ilike '%' || search_text || '%'
            or coalesce(movement.origin_location_name, '') ilike '%' || search_text || '%'
            or coalesce(movement.destination_location_id, '') ilike '%' || search_text || '%'
            or coalesce(movement.destination_location_name, '') ilike '%' || search_text || '%'
            or coalesce(movement.truck_plate, '') ilike '%' || search_text || '%'
            or coalesce(movement.driver_name, '') ilike '%' || search_text || '%'
            or coalesce(movement.trailer_plate, '') ilike '%' || search_text || '%'
            or coalesce(movement.load_type, '') ilike '%' || search_text || '%'
            or coalesce(movement.status, '') ilike '%' || search_text || '%'
        )
    ),
    page as (
        select *
        from eligible
        order by departure_at desc, id
        limit p_page_size
        offset (p_page::bigint - 1) * p_page_size
    )
    select
        (select count(*) from eligible),
        coalesce(
            jsonb_agg(
                to_jsonb(page_row)
                order by page_row.departure_at desc, page_row.id
            ),
            '[]'::jsonb
        )
    into total_count, page_rows
    from page as page_row;

    return jsonb_build_object('total', total_count, 'movements', page_rows);
end;
$$;

drop policy if exists dispatch_movements_read on public.dispatch_movements;
create policy dispatch_movements_read on public.dispatch_movements
    for select to authenticated using (
        public.dispatch_is_admin()
        or public.dispatch_has_location(origin_location_id, 'view')
        or (
            status <> 'completed'
            and public.dispatch_has_location(origin_location_id, 'depart')
        )
        or departure_user_id = auth.uid()
        or (
            departure_manifest_path is not null
            and public.dispatch_has_location(destination_location_id, 'view')
        )
    );

drop policy if exists dispatch_audit_read on public.dispatch_movement_audit;
create policy dispatch_audit_read on public.dispatch_movement_audit
    for select to authenticated using (
        public.dispatch_is_admin()
        or exists (
            select 1 from public.dispatch_movements as movement
            where movement.id = dispatch_movement_audit.movement_id
              and (
                  public.dispatch_has_location(movement.origin_location_id, 'view')
                  or (
                      movement.status <> 'completed'
                      and public.dispatch_has_location(movement.origin_location_id, 'depart')
                  )
                  or movement.departure_user_id = auth.uid()
                  or (
                      movement.departure_manifest_path is not null
                      and public.dispatch_has_location(movement.destination_location_id, 'view')
                  )
              )
        )
    );

drop policy if exists dispatch_movement_documents_read on storage.objects;
create policy dispatch_movement_documents_read on storage.objects
    for select to authenticated
    using (
        bucket_id = 'fleet-trip-documents'
        and name ~ '^[0-9a-fA-F-]{36}/(departure|arrival|fuel_invoice)/[A-Za-z0-9_-]+[.](jpg|png|webp)$'
        and exists (
            select 1 from public.dispatch_movements as movement
            where movement.id = split_part(name, '/', 1)::uuid
              and (
                  public.dispatch_is_admin()
                  or case split_part(name, '/', 2)
                      when 'departure' then
                          public.dispatch_has_location(movement.origin_location_id, 'view')
                          or movement.departure_user_id = auth.uid()
                          or movement.arrival_verified_by = auth.uid()
                      when 'arrival' then
                          public.dispatch_has_location(movement.origin_location_id, 'view')
                          or movement.arrival_verified_by = auth.uid()
                      when 'fuel_invoice' then
                          public.dispatch_has_location(movement.origin_location_id, 'view')
                          or movement.departure_user_id = auth.uid()
                          or movement.arrival_verified_by = auth.uid()
                      else false
                  end
              )
        )
    );

drop policy if exists dispatch_movement_documents_scope_guard on storage.objects;
create policy dispatch_movement_documents_scope_guard on storage.objects
    as restrictive
    for all to authenticated
    using (
        bucket_id <> 'fleet-trip-documents'
        or name !~ '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89aAbB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}/(departure|arrival|fuel_invoice)/[A-Za-z0-9_-]+[.](jpg|png|webp)$'
        or exists (
            select 1 from public.dispatch_movements as movement
            where movement.id = split_part(name, '/', 1)::uuid
              and case split_part(name, '/', 2)
                  when 'departure' then
                      public.dispatch_is_admin()
                      or movement.departure_user_id = auth.uid()
                      or movement.arrival_verified_by = auth.uid()
                  when 'fuel_invoice' then
                      public.dispatch_is_admin()
                      or movement.departure_user_id = auth.uid()
                      or movement.arrival_verified_by = auth.uid()
                  when 'arrival' then
                      public.dispatch_is_admin()
                      or (
                          movement.arrival_verified_by = auth.uid()
                          and public.dispatch_has_location(movement.destination_location_id, 'arrive')
                      )
                  else false
              end
        )
    )
    with check (
        bucket_id <> 'fleet-trip-documents'
        or name !~ '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89aAbB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}/(departure|arrival|fuel_invoice)/[A-Za-z0-9_-]+[.](jpg|png|webp)$'
        or exists (
            select 1 from public.dispatch_movements as movement
            where movement.id = split_part(name, '/', 1)::uuid
              and case split_part(name, '/', 2)
                  when 'departure' then
                      public.dispatch_is_admin()
                      or (
                          movement.departure_user_id = auth.uid()
                          and public.dispatch_has_location(movement.origin_location_id, 'depart')
                      )
                  when 'fuel_invoice' then
                      public.dispatch_is_admin()
                      or (
                          movement.departure_user_id = auth.uid()
                          and public.dispatch_has_location(movement.origin_location_id, 'depart')
                      )
                  when 'arrival' then
                      public.dispatch_is_admin()
                      or (
                          movement.arrival_verified_by = auth.uid()
                          and public.dispatch_has_location(movement.destination_location_id, 'arrive')
                      )
                  else false
              end
        )
    );

commit;
