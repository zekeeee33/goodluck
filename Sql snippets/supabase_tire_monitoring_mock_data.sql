-- Paste this into the Supabase SQL Editor after applying
-- supabase_tire_monitoring_migration.sql.
-- Adds eight clearly labeled sample records to the first truck found,
-- preferring plate UHZ 217 when it exists. Safe to rerun.

do $$
declare
    target_vehicle_id bigint;
begin
    select id
    into target_vehicle_id
    from public.vehicles
    order by case
        when regexp_replace(upper(plate_number), '[^A-Z0-9]', '', 'g') = 'UHZ217'
            then 0
        else 1
    end, id
    limit 1;

    if target_vehicle_id is null then
        raise exception
            'No truck exists for the sample tire records. Add a truck first, then rerun this script.';
    end if;

    insert into public.tire_monitoring (
        asset_type,
        vehicle_id,
        trailer_id,
        brand,
        size,
        tire_type,
        serial_no,
        supplier,
        date_installed,
        remaining_lifespan_pct,
        remarks,
        status
    )
    select
        'truck',
        target_vehicle_id,
        null,
        sample.brand,
        sample.size,
        sample.tire_type,
        sample.serial_no,
        null,
        sample.date_installed,
        sample.remaining_lifespan_pct,
        'SAMPLE DATA - safe to remove after testing',
        'installed'
    from (
        values
            (
                'SUN LIFE'::text,
                '11R22.5'::text,
                'TUBELESS'::text,
                'MOCK-UHZ217-SUNLIFE-001'::text,
                date '2026-09-08',
                100.00::numeric
            ),
            (
                'C LONG POWER'::text,
                '11R22.5'::text,
                'DRIVE'::text,
                'MOCK-UHZ217-CLONG-002'::text,
                date '2026-09-08',
                95.00::numeric
            ),
            (
                'SUN LIFE'::text,
                '11R22.5'::text,
                'DRIVE'::text,
                'MOCK-UHZ217-SUNLIFE-003'::text,
                date '2026-08-20',
                88.00::numeric
            ),
            (
                'C LONG POWER'::text,
                '11R22.5'::text,
                'DRIVE'::text,
                'MOCK-UHZ217-CLONG-004'::text,
                date '2026-08-20',
                82.00::numeric
            ),
            (
                'BRIDGESTONE'::text,
                '11R22.5'::text,
                'STEER'::text,
                'MOCK-UHZ217-BRIDGE-005'::text,
                date '2026-07-14',
                76.50::numeric
            ),
            (
                'MICHELIN'::text,
                '11R22.5'::text,
                'STEER'::text,
                'MOCK-UHZ217-MICHELIN-006'::text,
                date '2026-07-14',
                69.00::numeric
            ),
            (
                'SUN LIFE'::text,
                '11R22.5'::text,
                'SPARE'::text,
                'MOCK-UHZ217-SUNLIFE-007'::text,
                date '2026-06-02',
                100.00::numeric
            ),
            (
                'GOODYEAR'::text,
                '11R22.5'::text,
                'DRIVE'::text,
                'MOCK-UHZ217-GOODYEAR-008'::text,
                date '2026-05-18',
                54.00::numeric
            )
    ) as sample(brand, size, tire_type, serial_no, date_installed, remaining_lifespan_pct)
    where not exists (
        select 1
        from public.tire_monitoring existing
        where lower(btrim(existing.serial_no)) = lower(btrim(sample.serial_no))
    );
end;
$$;

select
    reference_no,
    brand,
    size,
    tire_type,
    serial_no,
    date_installed,
    remaining_lifespan_pct,
    status
from public.tire_monitoring
where serial_no in (
    'MOCK-UHZ217-SUNLIFE-001',
    'MOCK-UHZ217-CLONG-002',
    'MOCK-UHZ217-SUNLIFE-003',
    'MOCK-UHZ217-CLONG-004',
    'MOCK-UHZ217-BRIDGE-005',
    'MOCK-UHZ217-MICHELIN-006',
    'MOCK-UHZ217-SUNLIFE-007',
    'MOCK-UHZ217-GOODYEAR-008'
)
order by serial_no;
