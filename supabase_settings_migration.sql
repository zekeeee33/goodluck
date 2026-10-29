begin;

create table if not exists public.driver_pay_rates (
    route_class text primary key
        check (route_class in ('short', 'long')),
    allowance numeric(12, 2) not null
        check (allowance >= 0),
    updated_at timestamptz not null default now()
);

insert into public.driver_pay_rates (route_class, allowance)
values ('short', 200.00), ('long', 900.00)
on conflict (route_class) do nothing;

alter table public.driver_pay_rates enable row level security;
alter table public.driver_pay_rates force row level security;
revoke all on table public.driver_pay_rates from public, anon, authenticated;
grant all on table public.driver_pay_rates to service_role;

create or replace function public.update_driver_pay_rates(
    p_short_allowance numeric,
    p_long_allowance numeric
)
returns setof public.driver_pay_rates
language sql
security definer
set search_path = ''
as $$
    insert into public.driver_pay_rates (route_class, allowance, updated_at)
    values
        ('short', p_short_allowance, now()),
        ('long', p_long_allowance, now())
    on conflict (route_class) do update
        set allowance = excluded.allowance,
            updated_at = excluded.updated_at
    returning *;
$$;

revoke all on function public.update_driver_pay_rates(numeric, numeric)
    from public, anon, authenticated;
grant execute on function public.update_driver_pay_rates(numeric, numeric)
    to service_role;

alter table public.truck_routes
    add column if not exists fuel_allocation numeric(12, 2)
    check (fuel_allocation is null or fuel_allocation >= 0);

commit;
