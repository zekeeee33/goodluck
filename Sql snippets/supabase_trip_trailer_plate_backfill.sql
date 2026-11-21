-- Recover trailer assignments stored in trips.plate_no when the value exactly
-- matches a registered trailer plate. This applies across all trip dates.

begin;

lock table public.trips in share row exclusive mode;

create temp table trip_trailer_backfill_stage on commit drop as
select
    trip.id as trip_id,
    trip.shipment_date,
    trip.driver_name,
    trip.plate_no as source_plate,
    trip.trailer_plate_no as current_trailer_plate,
    mapping.candidate_count,
    mapping.trailer_id as matched_trailer_id,
    mapping.trailer_plate as matched_trailer_plate
from public.trips as trip
cross join lateral (
    select
        count(*)::integer as candidate_count,
        min(trailer.id) as trailer_id,
        min(trailer.plate_number) as trailer_plate
    from public.trailers as trailer
    where upper(btrim(trailer.plate_number)) = upper(btrim(
        coalesce(nullif(trip.trailer_plate_no, ''), trip.plate_no)
    ))
) as mapping
where trip.trailer_id is null
  and nullif(btrim(coalesce(nullif(trip.trailer_plate_no, ''), trip.plate_no)), '') is not null;

update public.trips as trip
set trailer_id = stage.matched_trailer_id,
    trailer_plate_no = coalesce(nullif(trip.trailer_plate_no, ''), stage.matched_trailer_plate),
    trailer_review_required = false
from pg_temp.trip_trailer_backfill_stage as stage
where trip.id = stage.trip_id
  and stage.candidate_count = 1;

select
    stage.trip_id,
    stage.shipment_date,
    stage.driver_name,
    stage.source_plate,
    case
        when stage.candidate_count = 1 then 'ASSIGNED'
        when stage.candidate_count > 1 then 'AMBIGUOUS REGISTRY MATCH'
        else 'NO REGISTRY MATCH'
    end as result,
    case
        when stage.candidate_count = 1 then stage.matched_trailer_plate
        else null
    end as assigned_trailer_plate,
    stage.candidate_count
from pg_temp.trip_trailer_backfill_stage as stage
order by stage.shipment_date, stage.driver_name, stage.trip_id;

commit;
