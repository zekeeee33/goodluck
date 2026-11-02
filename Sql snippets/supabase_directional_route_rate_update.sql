begin;

do $$
declare
    updated_rows integer;
begin
    update public.truck_route_rates
    set hauling_rate = 12268.90,
        updated_at = now()
    where origin_code = 'GENSAN'
      and destination_code = 'DAV1'
      and pallet_capacity = 36;

    get diagnostics updated_rows = row_count;
    if updated_rows <> 1 then
        raise exception
            'Expected one GENSAN to DAV1 36-pallet rate row, updated %',
            updated_rows;
    end if;
end;
$$;

commit;
