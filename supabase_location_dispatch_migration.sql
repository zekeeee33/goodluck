-- Add a location-scoped departure/arrival workflow without changing historical
-- trips. A completed movement is linked to exactly one canonical public.trips row.
-- Apply after the existing trips, route/rate, dispatcher ownership, and payroll
-- migrations.

create table if not exists public.dispatch_locations (
    id text primary key,
    name text not null,
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint dispatch_locations_id_format check (id = upper(trim(id)) and id <> '')
);

insert into public.dispatch_locations (id, name)
select location_id, max(location_name)
from (
    select origin_code as location_id, origin_name as location_name
    from public.truck_routes
    union all
    select destination_code, destination_name
    from public.truck_routes
) as locations
group by location_id
on conflict (id) do update
set name = excluded.name,
    updated_at = now();

create table if not exists public.dispatcher_location_assignments (
    user_id uuid not null references auth.users(id) on delete cascade,
    location_id text not null references public.dispatch_locations(id),
    can_depart boolean not null default true,
    can_arrive boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    primary key (user_id, location_id)
);

-- Map active dispatcher profiles D1-D6 to DAV1-DAV6. Location access is limited
-- by this admin-managed profile mapping; a metadata role alone grants no access.
do $$
begin
    if to_regclass('public.users') is not null
       and exists (
           select 1 from information_schema.columns
           where table_schema = 'public' and table_name = 'users'
             and column_name in ('id', 'role', 'dispatcher_code', 'status')
           group by table_name
           having count(*) = 4
       ) then
        execute $map_locations$
            insert into public.dispatch_locations (id, name)
            select 'DAV' || substring(upper(trim(profile.dispatcher_code)) from 2),
                   'DAV' || substring(upper(trim(profile.dispatcher_code)) from 2)
            from public.users as profile
            where lower(trim(profile.role)) = 'dispatcher'
              and lower(trim(profile.status)) = 'active'
              and upper(trim(profile.dispatcher_code)) ~ '^D[1-6]$'
            on conflict (id) do nothing
        $map_locations$;

        execute $map_assignments$
            insert into public.dispatcher_location_assignments (
                user_id, location_id, can_depart, can_arrive
            )
            select auth_user.id,
                   'DAV' || substring(upper(trim(profile.dispatcher_code)) from 2),
                   true, true
            from public.users as profile
            join auth.users as auth_user on auth_user.id = profile.id
            join public.dispatch_locations as location
              on location.id = 'DAV' || substring(upper(trim(profile.dispatcher_code)) from 2)
             and location.active
            where lower(trim(profile.role)) = 'dispatcher'
              and lower(trim(profile.status)) = 'active'
              and upper(trim(profile.dispatcher_code)) ~ '^D[1-6]$'
            on conflict (user_id, location_id) do update set
                can_depart = excluded.can_depart,
                can_arrive = excluded.can_arrive,
                updated_at = now()
        $map_assignments$;
    end if;
end;
$$;

create table if not exists public.dispatch_movements (
    id uuid primary key default gen_random_uuid(),
    origin_location_id text not null references public.dispatch_locations(id),
    destination_location_id text not null references public.dispatch_locations(id),
    ism_no text not null,
    truck_id bigint not null references public.vehicles(id),
    driver_id bigint not null references public.drivers(id),
    trailer_id bigint not null references public.trailers(id),
    load_type text not null check (load_type in ('FULLS', 'EMPTIES')),
    pallet_quantity integer not null check (pallet_quantity > 0),
    departure_at timestamptz not null,
    departure_user_id uuid not null references auth.users(id),
    departure_manifest_path text,
    fuel_allocation numeric(12, 2) check (fuel_allocation is null or fuel_allocation >= 0),
    actual_fuel_expense numeric(12, 2) check (actual_fuel_expense is null or actual_fuel_expense >= 0),
    fuel_remarks text,
    fuel_invoice_path text,
    arrival_verified_at timestamptz,
    arrival_verified_by uuid references auth.users(id),
    arrival_at timestamptz,
    arrival_user_id uuid references auth.users(id),
    arrival_manifest_path text,
    arrival_fuel_expense numeric(12, 2) check (arrival_fuel_expense is null or arrival_fuel_expense >= 0),
    status text not null default 'awaiting_arrival'
        check (status in (
            'awaiting_arrival', 'arrival_submitted', 'needs_correction', 'completed'
        )),
    canonical_trip_id bigint unique references public.trips(id) on delete restrict,
    finalized_at timestamptz,
    finalized_by uuid references auth.users(id),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint dispatch_movements_distinct_locations
        check (origin_location_id <> destination_location_id),
    constraint dispatch_movements_verification_pair
        check ((arrival_verified_at is null) = (arrival_verified_by is null)),
    constraint dispatch_movements_arrival_pair
        check ((arrival_at is null) = (arrival_user_id is null)),
    constraint dispatch_movements_finalization_pair
        check (
            (status = 'completed')
            = (canonical_trip_id is not null and finalized_at is not null and finalized_by is not null)
        )
);

alter table public.trips
    add column if not exists dispatch_movement_id uuid;

create unique index if not exists trips_dispatch_movement_id_unique
    on public.trips(dispatch_movement_id)
    where dispatch_movement_id is not null;

do $$
begin
    if not exists (
        select 1 from pg_constraint
        where conname = 'trips_dispatch_movement_id_fkey'
          and conrelid = 'public.trips'::regclass
    ) then
        alter table public.trips
            add constraint trips_dispatch_movement_id_fkey
            foreign key (dispatch_movement_id)
            references public.dispatch_movements(id)
            on delete restrict;
    end if;
end;
$$;

create index if not exists dispatch_movements_origin_queue_idx
    on public.dispatch_movements(origin_location_id, status, departure_at desc);
create index if not exists dispatch_movements_destination_queue_idx
    on public.dispatch_movements(destination_location_id, status, departure_at desc);
create unique index if not exists dispatch_movements_ism_unique
    on public.dispatch_movements(lower(trim(ism_no)));
create index if not exists dispatcher_location_assignments_user_idx
    on public.dispatcher_location_assignments(user_id, location_id);

create table if not exists public.dispatch_movement_audit (
    id bigint generated always as identity primary key,
    movement_id uuid not null references public.dispatch_movements(id) on delete restrict,
    actor_id uuid references auth.users(id) on delete set null,
    action text not null,
    details jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists dispatch_movement_audit_movement_created_idx
    on public.dispatch_movement_audit(movement_id, created_at desc);

create or replace function public.dispatch_is_admin()
returns boolean
language sql
stable
security definer
set search_path = pg_catalog, auth, pg_temp
as $$
    select coalesce(auth.jwt() -> 'app_metadata' ->> 'role', '') = 'administrator'
       and coalesce(auth.jwt() -> 'user_metadata' ->> 'role', '') <> 'dispatcher';
$$;

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
                select 1 from public.dispatch_locations as location
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

create or replace function public.dispatch_log_event(
    p_movement_id uuid,
    p_action text,
    p_details jsonb default '{}'::jsonb
)
returns void
language sql
security definer
set search_path = pg_catalog, public, auth, pg_temp
as $$
    insert into public.dispatch_movement_audit (movement_id, actor_id, action, details)
    values (p_movement_id, auth.uid(), p_action, coalesce(p_details, '{}'::jsonb));
$$;

create or replace function public.dispatch_protect_audit()
returns trigger
language plpgsql
set search_path = pg_catalog, public, pg_temp
as $$
begin
    raise exception 'Dispatch audit events are immutable';
end;
$$;

create or replace function public.list_dispatcher_users()
returns table (user_id uuid, email text, full_name text)
language plpgsql
stable
security definer
set search_path = pg_catalog, auth, pg_temp
as $$
begin
    if not public.dispatch_is_admin() then
        raise exception 'Only an administrator can list dispatcher accounts';
    end if;
    return query
    select users.id, users.email::text,
        coalesce(users.raw_user_meta_data ->> 'full_name', users.raw_user_meta_data ->> 'name')
    from auth.users as users
    where users.raw_app_meta_data ->> 'role' = 'dispatcher'
       or users.raw_user_meta_data ->> 'role' = 'dispatcher'
    order by users.email;
end;
$$;

create or replace function public.manage_dispatch_location(
    p_location_id text,
    p_name text,
    p_active boolean
)
returns void
language plpgsql
security definer
set search_path = pg_catalog, public, auth, pg_temp
as $$
begin
    if not public.dispatch_is_admin() then
        raise exception 'Only an administrator can manage dispatch locations';
    end if;
    if nullif(trim(p_location_id), '') is null or p_location_id <> upper(trim(p_location_id))
       or nullif(trim(p_name), '') is null then
        raise exception 'Enter a stable uppercase location ID and display name';
    end if;
    insert into public.dispatch_locations (id, name, active)
    values (p_location_id, trim(p_name), coalesce(p_active, true))
    on conflict (id) do update set
        name = excluded.name,
        active = excluded.active,
        updated_at = now();
end;
$$;

create or replace function public.list_dispatch_locations()
returns table (
    id text,
    name text,
    active boolean,
    can_depart boolean,
    can_arrive boolean
)
language plpgsql
stable
security definer
set search_path = pg_catalog, public, auth, pg_temp
as $$
begin
    if auth.uid() is null then raise exception 'Authentication required'; end if;
    return query
    select location.id, location.name, location.active,
        public.dispatch_has_location(location.id, 'depart'),
        public.dispatch_has_location(location.id, 'arrive')
    from public.dispatch_locations as location
    where location.active
    order by location.name;
end;
$$;

create or replace function public.request_dispatch_correction(
    p_movement_id uuid,
    p_reason text
)
returns void
language plpgsql
security definer
set search_path = pg_catalog, public, auth, pg_temp
as $$
declare
    movement public.dispatch_movements%rowtype;
begin
    if not public.dispatch_is_admin() then
        raise exception 'Only an administrator can request a correction';
    end if;
    select * into movement from public.dispatch_movements
    where id = p_movement_id for update;
    if not found or movement.status not in ('arrival_submitted', 'needs_correction') then
        raise exception 'Movement is not awaiting review';
    end if;
    if nullif(trim(p_reason), '') is null then
        raise exception 'A correction reason is required';
    end if;
    perform public.dispatch_log_event(
        p_movement_id, 'correction_requested',
        jsonb_build_object(
            'reason', trim(p_reason),
            'previous_arrival_at', movement.arrival_at,
            'previous_arrival_manifest_path', movement.arrival_manifest_path
        )
    );
    update public.dispatch_movements
    set status = 'needs_correction',
        updated_at = now(),
        arrival_at = null,
        arrival_user_id = null,
        arrival_manifest_path = null,
        arrival_fuel_expense = null
    where id = p_movement_id;
end;
$$;

drop trigger if exists dispatch_movement_audit_immutable on public.dispatch_movement_audit;
create trigger dispatch_movement_audit_immutable
    before update or delete on public.dispatch_movement_audit
    for each row execute function public.dispatch_protect_audit();

alter table public.dispatch_locations enable row level security;
alter table public.dispatcher_location_assignments enable row level security;
alter table public.dispatch_movements enable row level security;
alter table public.dispatch_movement_audit enable row level security;

drop policy if exists dispatch_locations_read on public.dispatch_locations;
create policy dispatch_locations_read on public.dispatch_locations
    for select to authenticated using (
        active and (
            public.dispatch_is_admin()
            or exists (
                select 1 from public.dispatcher_location_assignments as assignment
                where assignment.user_id = auth.uid()
                  and assignment.location_id = dispatch_locations.id
            )
        )
    );
drop policy if exists dispatch_locations_admin_write on public.dispatch_locations;
create policy dispatch_locations_admin_write on public.dispatch_locations
    for all to authenticated
    using (public.dispatch_is_admin())
    with check (public.dispatch_is_admin());

drop policy if exists dispatcher_assignments_read on public.dispatcher_location_assignments;
create policy dispatcher_assignments_read on public.dispatcher_location_assignments
    for select to authenticated using (
        public.dispatch_is_admin() or user_id = auth.uid()
    );
drop policy if exists dispatcher_assignments_admin_write on public.dispatcher_location_assignments;
create policy dispatcher_assignments_admin_write on public.dispatcher_location_assignments
    for all to authenticated
    using (public.dispatch_is_admin())
    with check (public.dispatch_is_admin());

drop policy if exists dispatch_movements_read on public.dispatch_movements;
create policy dispatch_movements_read on public.dispatch_movements
    for select to authenticated using (
        public.dispatch_is_admin()
        or public.dispatch_has_location(origin_location_id, 'view')
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
                  or movement.departure_user_id = auth.uid()
                  or (
                      movement.departure_manifest_path is not null
                      and public.dispatch_has_location(movement.destination_location_id, 'view')
                  )
              )
        )
    );

-- Expected ISM is never exposed through a direct table read. RPCs are the only
-- way to submit or reveal it, and only a verified receiver can receive details.
revoke all on public.dispatch_movements from anon, authenticated;
grant select (
    id, origin_location_id, destination_location_id, truck_id, driver_id, trailer_id,
    load_type, pallet_quantity, departure_at, departure_user_id,
    fuel_allocation, actual_fuel_expense, fuel_remarks,
    arrival_verified_at, arrival_verified_by, arrival_at, arrival_user_id,
    arrival_fuel_expense, status, canonical_trip_id,
    finalized_at, finalized_by, created_at, updated_at
) on public.dispatch_movements to authenticated;
revoke all on public.dispatch_movement_audit from anon, authenticated;
grant select on public.dispatch_movement_audit to authenticated;
revoke insert, update, delete on public.dispatch_locations,
    public.dispatcher_location_assignments from anon, authenticated;
grant select on public.dispatch_locations, public.dispatcher_location_assignments
    to authenticated;

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
              or public.dispatch_has_location(movement.origin_location_id, 'view')
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
              or public.dispatch_has_location(movement.origin_location_id, 'view')
              or movement.departure_user_id = auth.uid()
              or movement.arrival_verified_by = auth.uid()
            then movement.departure_manifest_path
            else null
        end,
        movement.departure_manifest_path is not null,
        case
            when public.dispatch_is_admin()
              or public.dispatch_has_location(movement.origin_location_id, 'view')
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
       or movement.departure_user_id = auth.uid()
       or (
           movement.departure_manifest_path is not null
           and public.dispatch_has_location(movement.destination_location_id, 'view')
       )
    order by movement.created_at desc;
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
       or p_load_type is null or p_load_type not in ('FULLS', 'EMPTIES')
       or p_pallet_quantity is null or p_pallet_quantity < 1 then
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

    with eligible as (
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
    )
    select count(*) into total_count from eligible;

    with eligible as (
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
    )
    select coalesce(jsonb_agg(to_jsonb(page_row)), '[]'::jsonb)
    into page_rows
    from (
        select * from eligible
        order by departure_at desc, id
        limit p_page_size
        offset (p_page::bigint - 1) * p_page_size
    ) as page_row;

    return jsonb_build_object('total', total_count, 'movements', page_rows);
end;
$$;

create or replace function public.attach_dispatch_document(
    p_movement_id uuid,
    p_document_kind text,
    p_object_path text
)
returns void
language plpgsql
security definer
set search_path = pg_catalog, public, auth, pg_temp
as $$
declare
    movement public.dispatch_movements%rowtype;
begin
    select * into movement
    from public.dispatch_movements
    where id = p_movement_id
    for update;
    if not found then raise exception 'Movement not found'; end if;
    if p_document_kind is null or p_object_path is null
       or p_document_kind not in ('departure', 'arrival', 'fuel_invoice')
       or p_object_path !~ ('^' || p_movement_id::text || '/' || p_document_kind || '/[A-Za-z0-9_-]+[.](' || 'jpg|png|webp' || ')$') then
        raise exception 'Invalid movement document path';
    end if;
    if p_document_kind in ('departure', 'fuel_invoice') then
        if not public.dispatch_has_location(movement.origin_location_id, 'depart')
           or movement.departure_user_id <> auth.uid() then
            raise exception 'Only the originating dispatcher can attach departure documents';
        end if;
        if p_document_kind = 'departure' then
            update public.dispatch_movements set departure_manifest_path = p_object_path,
                updated_at = now() where id = p_movement_id;
        else
            update public.dispatch_movements set fuel_invoice_path = p_object_path,
                updated_at = now() where id = p_movement_id;
        end if;
    else
        if not public.dispatch_has_location(movement.destination_location_id, 'arrive')
           or movement.arrival_verified_by is distinct from auth.uid()
           or movement.arrival_verified_at is null
           or movement.status not in ('awaiting_arrival', 'needs_correction') then
            raise exception 'Only the verified receiving dispatcher can attach arrival documents';
        end if;
        update public.dispatch_movements set arrival_manifest_path = p_object_path,
            updated_at = now() where id = p_movement_id;
    end if;
    perform public.dispatch_log_event(
        p_movement_id, 'document_uploaded',
        jsonb_build_object('kind', p_document_kind, 'object_path', p_object_path)
    );
end;
$$;

create or replace function public.verify_dispatch_ism(
    p_movement_id uuid,
    p_submitted_ism text
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public, auth, pg_temp
as $$
declare
    movement public.dispatch_movements%rowtype;
    matched boolean;
begin
    select * into movement
    from public.dispatch_movements
    where id = p_movement_id
    for update;
    if not found
       or not public.dispatch_has_location(movement.destination_location_id, 'arrive')
       or movement.status not in ('awaiting_arrival', 'needs_correction') then
        raise exception 'Movement is not available for arrival verification';
    end if;
    matched := nullif(trim(coalesce(p_submitted_ism, '')), '') is not null
        and lower(trim(p_submitted_ism)) = lower(trim(movement.ism_no));
    perform public.dispatch_log_event(
        p_movement_id,
        case when matched then 'ism_verified' else 'ism_verification_failed' end,
        jsonb_build_object('matched', matched)
    );
    if matched then
        update public.dispatch_movements
        set arrival_verified_at = now(),
            arrival_verified_by = auth.uid(),
            updated_at = now()
        where id = p_movement_id;
    end if;
    return jsonb_build_object('verified', matched);
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
begin
    select * into movement
    from public.dispatch_movements
    where id = p_movement_id
    for update;
    if not found
       or not public.dispatch_has_location(movement.destination_location_id, 'arrive')
       or movement.arrival_verified_by <> auth.uid()
       or movement.arrival_verified_at is null
       or movement.status not in ('awaiting_arrival', 'needs_correction') then
        raise exception 'Verify the ISM before submitting arrival';
    end if;
    if p_arrival_at is null or movement.departure_manifest_path is null
       or movement.arrival_manifest_path is null then
        raise exception 'Departure and arrival manifests and an arrival time are required';
    end if;
    if p_arrival_at < movement.departure_at then
        raise exception 'Arrival time cannot be earlier than departure time';
    end if;
    update public.dispatch_movements
    set arrival_at = p_arrival_at,
        arrival_user_id = auth.uid(),
        arrival_fuel_expense = p_arrival_fuel_expense,
        status = 'arrival_submitted',
        updated_at = now()
    where id = p_movement_id;
    perform public.dispatch_log_event(p_movement_id, 'arrival_submitted',
        jsonb_build_object('arrival_at', p_arrival_at));
end;
$$;

create or replace function public.finalize_dispatch_movement(p_movement_id uuid)
returns bigint
language plpgsql
security definer
set search_path = pg_catalog, public, auth, pg_temp
as $$
declare
    movement public.dispatch_movements%rowtype;
    route_row public.truck_routes%rowtype;
    trailer_capacity integer;
    rate_row public.truck_route_rates%rowtype;
    created_trip_id bigint;
    existing_trip_id bigint;
begin
    if not public.dispatch_is_admin() then
        raise exception 'Only an administrator can finalize movements';
    end if;
    select * into movement
    from public.dispatch_movements
    where id = p_movement_id
    for update;
    if not found then raise exception 'Movement not found'; end if;
    if movement.canonical_trip_id is not null then
        return movement.canonical_trip_id;
    end if;
    if movement.status <> 'arrival_submitted'
       or movement.arrival_verified_at is null
       or movement.arrival_at is null
       or movement.departure_manifest_path is null
       or movement.arrival_manifest_path is null then
        raise exception 'Movement is not ready for finalization';
    end if;

    select * into route_row
    from public.truck_routes
    where origin_code = movement.origin_location_id
      and destination_code = movement.destination_location_id
      and active;
    if not found then raise exception 'No active route is configured for this movement'; end if;

    select pallet_capacity into trailer_capacity
    from public.trailers where id = movement.trailer_id;
    if trailer_capacity is null then
        raise exception 'Trailer pallet capacity must be configured before finalization';
    end if;
    if movement.pallet_quantity > trailer_capacity then
        raise exception 'Pallet quantity exceeds trailer capacity';
    end if;
    select * into rate_row
    from public.truck_route_rates
    where route_id = route_row.id
      and pallet_capacity = trailer_capacity
      and active
      and hauling_rate is not null
    limit 1;
    if not found then
        raise exception 'An active hauling rate for this route and trailer capacity is required';
    end if;

    select id into existing_trip_id
    from public.trips
    where dispatch_movement_id = movement.id;
    if existing_trip_id is not null then
        update public.dispatch_movements
        set canonical_trip_id = existing_trip_id,
            status = 'completed',
            finalized_at = coalesce(finalized_at, now()),
            finalized_by = coalesce(finalized_by, auth.uid()),
            updated_at = now()
        where id = movement.id;
        return existing_trip_id;
    end if;

    insert into public.trips (
        vehicle_id, truck_id, trailer_id, driver_id, route, start_odometer,
        end_odometer, trip_date, shipment_date, ism_no, time_out, time_in,
        origin, destination, route_id, route_number, route_pair, pallet_capacity,
        truck_route_rate_id, truck_route_rate, trip_rate_review_required,
        trailer_review_required, load_details, dispatch_movement_id, created_by,
        manifest_object_path
    ) values (
        movement.truck_id, movement.truck_id, movement.trailer_id, movement.driver_id,
        route_row.origin_name || ' to ' || route_row.destination_name, 0, 0,
        (movement.departure_at at time zone 'Asia/Manila')::date,
        (movement.departure_at at time zone 'Asia/Manila')::date,
        movement.ism_no,
        (movement.departure_at at time zone 'Asia/Manila')::time,
        (movement.arrival_at at time zone 'Asia/Manila')::time,
        route_row.origin_name, route_row.destination_name, route_row.id,
        route_row.route_number, route_row.route_pair, trailer_capacity,
        rate_row.id, rate_row.hauling_rate, false, false,
        movement.load_type || ' — ' || movement.pallet_quantity || ' pallets',
        movement.id, movement.departure_user_id, movement.departure_manifest_path
    ) returning id into created_trip_id;

    if movement.fuel_allocation is not null
       or movement.actual_fuel_expense is not null
       or movement.arrival_fuel_expense is not null
       or movement.fuel_remarks is not null
       or movement.fuel_invoice_path is not null then
        insert into public.fuel_logs (
            vehicle_id, trip_id, fuel_type, total_cost, fuel_allocation,
            actual_expense, invoice_object_path, remarks, logged_on, created_by
        ) values (
            movement.truck_id, created_trip_id, 'diesel',
            coalesce(movement.actual_fuel_expense, 0)
                + coalesce(movement.arrival_fuel_expense, 0),
            movement.fuel_allocation,
            coalesce(movement.actual_fuel_expense, 0)
                + coalesce(movement.arrival_fuel_expense, 0),
            movement.fuel_invoice_path,
            movement.fuel_remarks,
            (movement.departure_at at time zone 'Asia/Manila')::date,
            movement.departure_user_id
        );
    end if;

    update public.dispatch_movements
    set canonical_trip_id = created_trip_id,
        status = 'completed',
        finalized_at = now(),
        finalized_by = auth.uid(),
        updated_at = now()
    where id = movement.id;
    perform public.dispatch_log_event(movement.id, 'movement_finalized',
        jsonb_build_object('canonical_trip_id', created_trip_id));
    return created_trip_id;
end;
$$;

create or replace function public.manage_dispatch_location_assignment(
    p_user_id uuid,
    p_location_id text,
    p_can_depart boolean,
    p_can_arrive boolean
)
returns void
language plpgsql
security definer
set search_path = pg_catalog, public, auth, pg_temp
as $$
begin
    if not public.dispatch_is_admin() then
        raise exception 'Only an administrator can manage dispatcher assignments';
    end if;
    if not exists (select 1 from public.dispatch_locations where id = p_location_id and active) then
        raise exception 'Select an active location';
    end if;
    if not exists (
        select 1 from auth.users
        where id = p_user_id
          and (
              raw_app_meta_data ->> 'role' = 'dispatcher'
              or raw_user_meta_data ->> 'role' = 'dispatcher'
          )
    ) then
        raise exception 'Select an account with the trusted dispatcher role';
    end if;
    insert into public.dispatcher_location_assignments (
        user_id, location_id, can_depart, can_arrive
    ) values (p_user_id, p_location_id, coalesce(p_can_depart, false), coalesce(p_can_arrive, false))
    on conflict (user_id, location_id) do update set
        can_depart = excluded.can_depart,
        can_arrive = excluded.can_arrive,
        updated_at = now();
end;
$$;

create or replace function public.list_dispatcher_assignments()
returns table (
    user_id uuid,
    email text,
    location_id text,
    location_name text,
    can_depart boolean,
    can_arrive boolean
)
language plpgsql
stable
security definer
set search_path = pg_catalog, public, auth, pg_temp
as $$
begin
    if not public.dispatch_is_admin() then
        raise exception 'Only an administrator can list dispatcher assignments';
    end if;
    return query
    select assignment.user_id, users.email::text, assignment.location_id,
        location.name, assignment.can_depart, assignment.can_arrive
    from public.dispatcher_location_assignments as assignment
    join public.dispatch_locations as location on location.id = assignment.location_id
    join auth.users as users on users.id = assignment.user_id
    order by location.name, users.email;
end;
$$;

-- A movement's documents live at <movement uuid>/<kind>/<generated filename>.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values (
    'fleet-trip-documents', 'fleet-trip-documents', false, 52428800,
    array['image/jpeg', 'image/png', 'image/webp']
)
on conflict (id) do update
set public = false,
    file_size_limit = greatest(storage.buckets.file_size_limit, excluded.file_size_limit),
    allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists dispatch_movement_documents_insert on storage.objects;
create policy dispatch_movement_documents_insert on storage.objects
    for insert to authenticated
    with check (
        bucket_id = 'fleet-trip-documents'
        and name ~ '^[0-9a-fA-F-]{36}/(departure|arrival|fuel_invoice)/[A-Za-z0-9_-]+[.](jpg|png|webp)$'
        and exists (
            select 1 from public.dispatch_movements as movement
            where movement.id = split_part(name, '/', 1)::uuid
              and (
                  (
                      split_part(name, '/', 2) in ('departure', 'fuel_invoice')
                      and movement.departure_user_id = auth.uid()
                      and public.dispatch_has_location(movement.origin_location_id, 'depart')
                  )
                  or (
                      split_part(name, '/', 2) = 'arrival'
                      and movement.arrival_verified_by = auth.uid()
                      and public.dispatch_has_location(movement.destination_location_id, 'arrive')
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
                      or (
                          movement.departure_user_id = auth.uid()
                          and public.dispatch_has_location(movement.origin_location_id, 'depart')
                      )
                      or movement.arrival_verified_by = auth.uid()
                  when 'fuel_invoice' then
                      public.dispatch_is_admin()
                      or movement.departure_user_id = auth.uid()
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

revoke all on function public.dispatch_is_admin() from public, anon;
revoke all on function public.dispatch_has_location(text, text) from public, anon;
revoke all on function public.dispatch_log_event(uuid, text, jsonb) from public, anon, authenticated;
revoke all on function public.dispatch_protect_audit() from public, anon, authenticated;
revoke all on function public.list_dispatch_movements() from public, anon;
revoke all on function public.list_dispatch_movements_page(text, integer, integer, text) from public, anon;
revoke all on function public.create_dispatch_movement(text, text, text, bigint, bigint, bigint, text, integer, timestamptz, numeric, numeric, text) from public, anon;
revoke all on function public.attach_dispatch_document(uuid, text, text) from public, anon;
revoke all on function public.verify_dispatch_ism(uuid, text) from public, anon;
revoke all on function public.submit_dispatch_arrival(uuid, timestamptz, numeric) from public, anon;
revoke all on function public.finalize_dispatch_movement(uuid) from public, anon;
revoke all on function public.manage_dispatch_location_assignment(uuid, text, boolean, boolean) from public, anon;
revoke all on function public.list_dispatcher_assignments() from public, anon;
revoke all on function public.manage_dispatch_location(text, text, boolean) from public, anon;
revoke all on function public.list_dispatch_locations() from public, anon;
revoke all on function public.list_dispatcher_users() from public, anon;
revoke all on function public.request_dispatch_correction(uuid, text) from public, anon;

grant execute on function public.dispatch_is_admin() to authenticated;
grant execute on function public.dispatch_has_location(text, text) to authenticated;
grant execute on function public.list_dispatch_movements() to authenticated;
grant execute on function public.list_dispatch_movements_page(text, integer, integer, text) to authenticated;
grant execute on function public.create_dispatch_movement(text, text, text, bigint, bigint, bigint, text, integer, timestamptz, numeric, numeric, text) to authenticated;
grant execute on function public.attach_dispatch_document(uuid, text, text) to authenticated;
grant execute on function public.verify_dispatch_ism(uuid, text) to authenticated;
grant execute on function public.submit_dispatch_arrival(uuid, timestamptz, numeric) to authenticated;
grant execute on function public.finalize_dispatch_movement(uuid) to authenticated;
grant execute on function public.manage_dispatch_location_assignment(uuid, text, boolean, boolean) to authenticated;
grant execute on function public.list_dispatcher_assignments() to authenticated;
grant execute on function public.manage_dispatch_location(text, text, boolean) to authenticated;
grant execute on function public.list_dispatch_locations() to authenticated;
grant execute on function public.list_dispatcher_users() to authenticated;
grant execute on function public.request_dispatch_correction(uuid, text) to authenticated;

comment on table public.dispatch_movements is
    'Location-scoped movement workflow. Its ISM is withheld from direct authenticated table reads; only security-checked RPCs may reveal it.';
comment on column public.trips.dispatch_movement_id is
    'Unique source movement for a finalized dispatcher workflow. NULL for historical trips.';
