-- DESTRUCTIVE ONE-TIME RESET: permanently removes all trip records and
-- trip-linked payroll/revenue data. Run manually in the Supabase SQL Editor
-- only after confirming these are test records and taking a database backup.
--
-- Fuel logs are preserved; their trip_id is set to NULL by the existing
-- foreign key. Payroll periods, cash advances, and overdraft records are kept.
-- The immutable revenue-audit triggers are removed only inside this
-- transaction and are recreated before commit.

begin;

drop trigger if exists trip_revenue_status_history_immutable
    on public.trip_revenue_status_history;
drop trigger if exists revenue_adjustments_immutable
    on public.revenue_adjustments;

delete from public.revenue_adjustments
where trip_id in (select id from public.trips);

delete from public.trip_revenue_status_history
where trip_id in (select id from public.trips);

delete from public.payroll_summaries
where payroll_period_id in (
    select distinct payroll_period_id
    from public.payroll_items
    where trip_id in (select id from public.trips)
);

delete from public.payroll_items
where trip_id in (select id from public.trips);

delete from public.legacy_trip_rate_review
where trip_id in (select id from public.trips);

delete from public.trips;

create trigger trip_revenue_status_history_immutable
    before update or delete on public.trip_revenue_status_history
    for each row execute function public.prevent_revenue_audit_mutation();

create trigger revenue_adjustments_immutable
    before update or delete on public.revenue_adjustments
    for each row execute function public.prevent_revenue_audit_mutation();

commit;

select
    (select count(*) from public.trips) as remaining_trips,
    (select count(*) from public.payroll_items) as remaining_payroll_items,
    (select count(*) from public.revenue_adjustments) as remaining_revenue_adjustments,
    (select count(*) from public.trip_revenue_status_history) as remaining_trip_revenue_history;
