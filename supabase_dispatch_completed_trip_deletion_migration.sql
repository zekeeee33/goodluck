-- Run after supabase_location_dispatch_migration.sql and the payroll/revenue
-- migrations. This allows administrators to remove a completed movement and
-- its generated trip while retaining protections on payroll/revenue records.

create or replace function public.dispatch_protect_audit()
returns trigger
language plpgsql
set search_path = pg_catalog, public, pg_temp
as $$
begin
    if tg_op = 'DELETE'
       and current_setting('app.allow_dispatch_audit_delete', true) = 'on'
       and public.dispatch_is_admin() then
        return old;
    end if;
    raise exception 'Dispatch audit events are immutable';
end;
$$;

create or replace function public.delete_completed_dispatch_movement(
    p_movement_id uuid
)
returns jsonb
language plpgsql
security definer
set search_path = pg_catalog, public, auth, pg_temp
as $$
declare
    movement public.dispatch_movements%rowtype;
    trip_id bigint;
    document_paths jsonb;
begin
    if not public.dispatch_is_admin() then
        raise exception 'Only an administrator can delete completed trips';
    end if;

    select * into movement
    from public.dispatch_movements
    where id = p_movement_id
    for update;
    if not found then raise exception 'Completed trip not found'; end if;
    if movement.status <> 'completed' or movement.canonical_trip_id is null then
        raise exception 'Only completed trips can be deleted';
    end if;

    trip_id := movement.canonical_trip_id;
    select coalesce(jsonb_agg(document_path), '[]'::jsonb)
    into document_paths
    from unnest(array[
        movement.departure_manifest_path,
        movement.arrival_manifest_path,
        movement.fuel_invoice_path
    ]) as documents(document_path)
    where document_path is not null;

    perform set_config('app.allow_dispatch_audit_delete', 'on', true);
    delete from public.dispatch_movement_audit
    where movement_id = movement.id;

    update public.trips
    set dispatch_movement_id = null
    where id = trip_id and dispatch_movement_id = movement.id;

    update public.dispatch_movements
    set canonical_trip_id = null,
        status = 'arrival_submitted',
        finalized_at = null,
        finalized_by = null
    where id = movement.id;

    delete from public.trips where id = trip_id;
    delete from public.dispatch_movements where id = movement.id;

    return jsonb_build_object(
        'trip_id', trip_id,
        'document_paths', document_paths
    );
exception
    when foreign_key_violation then
        raise exception
            'This completed trip is referenced by payroll or other protected financial records and cannot be deleted.';
end;
$$;

revoke all on function public.delete_completed_dispatch_movement(uuid)
    from public, anon;
grant execute on function public.delete_completed_dispatch_movement(uuid)
    to authenticated;
