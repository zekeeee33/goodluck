-- Corrected import of the 38 trips from 2026-11-14 through 2026-11-18.
-- Source IDs are retained only in the temporary staging table. PostgreSQL generates
-- public.trips.id. The trip-count trigger assigns trip_count on insert.
-- Existing ISM conflicts are skipped and displayed for review. Other failed validation
-- aborts the transaction without committing any imported rows.

BEGIN;

LOCK TABLE public.trips IN SHARE ROW EXCLUSIVE MODE;

CREATE TEMP TABLE trip_import_stage (
    source_id bigint,
    vehicle_id bigint,
    driver_id bigint,
    route text,
    start_odometer bigint,
    end_odometer bigint,
    trip_date date,
    notes text,
    ism_no text,
    shipment_date date,
    time_in time without time zone,
    time_out time without time zone,
    origin text,
    destination text,
    load_details text,
    trip_fuel text,
    record_date date,
    plate_no text,
    driver_name text,
    created_by uuid,
    updated_by uuid,
    manifest_object_path text,
    last_edited_by uuid,
    last_edited_by_email text,
    route_id bigint,
    route_number integer,
    route_pair text,
    pallet_capacity integer,
    truck_route_rate_id bigint,
    truck_route_rate numeric(12,2),
    trip_rate_review_required boolean,
    truck_id bigint,
    trailer_id bigint,
    trailer_review_required boolean,
    revenue_status text,
    dispatch_movement_id uuid,
    completed_trip_id bigint,
    trailer_plate_no text,
    skip_reason text,
    inserted_id bigint
) ON COMMIT DROP;

INSERT INTO pg_temp.trip_import_stage (
    source_id,
    vehicle_id,
    driver_id,
    route,
    start_odometer,
    end_odometer,
    trip_date,
    notes,
    ism_no,
    shipment_date,
    time_in,
    time_out,
    origin,
    destination,
    load_details,
    trip_fuel,
    record_date,
    plate_no,
    driver_name,
    created_by,
    updated_by,
    manifest_object_path,
    last_edited_by,
    last_edited_by_email,
    route_id,
    route_number,
    route_pair,
    pallet_capacity,
    truck_route_rate_id,
    truck_route_rate,
    trip_rate_review_required,
    truck_id,
    trailer_id,
    trailer_review_required,
    revenue_status,
    dispatch_movement_id,
    completed_trip_id,
    trailer_plate_no
)
VALUES
(696, NULL, NULL, 'GENSAN Distribution Center to PLAS Astorga', 0, 0, '2026-11-14', NULL, '32160259', '2026-11-14', '21:45:00', NULL, 'GENSAN Distribution Center', 'PLAS Astorga', '1P PALITA', NULL, CURRENT_DATE, 'LAS2006', 'NOLITO SAMARCA', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'GENSAN ↔ PLAS', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUB289'),
(697, NULL, NULL, 'PLAS Astorga to Davao Bottling Plant 2', 0, 0, '2026-11-14', NULL, '32211071', '2026-11-14', '11:35:00', '23:00:00', 'PLAS Astorga', 'Davao Bottling Plant 2', '46P COKE LITRO', NULL, CURRENT_DATE, 'LAS2006', 'NOLITO SAMARCA', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'DAV2 ↔ PLAS', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUB289'),
(698, NULL, NULL, 'Davao Bottling Plant 2 to GENSAN Distribution Center', 0, 0, '2026-11-15', NULL, '32198343', '2026-11-15', NULL, '12:15:00', 'Davao Bottling Plant 2', 'GENSAN Distribution Center', '46P COKE LITRO', NULL, CURRENT_DATE, 'LAS2006', 'NOLITO SAMARCA', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'GENSAN ↔ DAV2', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUB289'),
(699, NULL, NULL, 'GENSAN Distribution Center to PLAS Astorga', 0, 0, '2026-11-16', NULL, '32213793', '2026-11-16', '09:10:00', NULL, 'GENSAN Distribution Center', 'PLAS Astorga', '1P PALITA', NULL, CURRENT_DATE, 'NJI1511', 'JONATHAN MAMAC', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'GENSAN ↔ PLAS', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUA548'),
(700, NULL, NULL, 'PLAS Astorga to Davao Bottling Plant 2', 0, 0, '2026-11-16', NULL, '32204129', '2026-11-16', '10:37:00', '09:50:00', 'PLAS Astorga', 'Davao Bottling Plant 2', '1PALITA', NULL, CURRENT_DATE, 'NJI1511', 'JONATHAN MAMAC', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'DAV2 ↔ PLAS', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUA548'),
(701, NULL, NULL, 'GENSAN Distribution Center to PLAS Astorga', 0, 0, '2026-11-16', NULL, '32174524', '2026-11-16', '09:54:00', NULL, 'GENSAN Distribution Center', 'PLAS Astorga', '1P PALITA', NULL, CURRENT_DATE, 'LAO7425', 'RICHARD VALERA', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'GENSAN ↔ PLAS', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUB106'),
(702, NULL, NULL, 'PLAS Astorga to Davao Bottling Plant 2', 0, 0, '2026-11-16', NULL, '32204601', '2026-11-16', '10:50:00', '09:50:00', 'PLAS Astorga', 'Davao Bottling Plant 2', '1PALITA', NULL, CURRENT_DATE, 'LAO7425', 'RICHARD VALERA', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'DAV2 ↔ PLAS', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUB106'),
(703, NULL, NULL, 'PLAS Astorga to Davao Bottling Plant 2', 0, 0, '2026-11-14', NULL, '32187675', '2026-11-14', NULL, '23:00:00', 'PLAS Astorga', 'Davao Bottling Plant 2', '46P COKE LITRO', NULL, CURRENT_DATE, 'LAS2006', 'NOLITO SAMARCA', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'DAV2 ↔ PLAS', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUB289'),
(704, NULL, NULL, 'Davao Bottling Plant 2 to PLAS Astorga', 0, 0, '2026-11-16', 'HUSTLING', '32131119', '2026-11-16', NULL, '12:10:00', 'Davao Bottling Plant 2', 'PLAS Astorga', '46P COKE LITRO', NULL, CURRENT_DATE, 'NJI1511', 'JONATHAN MAMAC', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'DAV2 ↔ PLAS', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUA548'),
(705, NULL, NULL, 'Davao Bottling Plant 2 to PLAS Astorga', 0, 0, '2026-11-16', 'HUSTLING', '32204809', '2026-11-16', '12:35:00', '12:20:00', 'Davao Bottling Plant 2', 'PLAS Astorga', '46P COKE LITRO', NULL, CURRENT_DATE, 'LAO7425', 'RICHARD VALERA', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'DAV2 ↔ PLAS', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUB106'),
(706, NULL, NULL, 'GENSAN Distribution Center to PLAS Astorga', 0, 0, '2026-11-16', NULL, '32160256', '2026-11-16', '12:40:00', NULL, 'GENSAN Distribution Center', 'PLAS Astorga', '1P PALITA', NULL, CURRENT_DATE, 'MVG293', 'JOVEN JAY BAING', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'GENSAN ↔ PLAS', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUB282'),
(707, NULL, 4175, 'PLAS Astorga to Davao Bottling Plant 2', 0, 0, '2026-11-16', 'DR. 0044277', '32204604', '2026-11-16', '13:25:00', '13:15:00', 'PLAS Astorga', 'Davao Bottling Plant 2', '46P COKE LITRO', NULL, CURRENT_DATE, 'NJI1511', 'JONATHAN MAMAC', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'DAV2 ↔ PLAS', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUA548'),
(708, NULL, 8496, 'PLAS Astorga to Davao Bottling Plant 2', 0, 0, '2026-11-16', 'DR. 0044278', '32204605', '2026-11-16', '14:05:00', '13:50:00', 'PLAS Astorga', 'Davao Bottling Plant 2', '46P COKE LITRO', NULL, CURRENT_DATE, 'LAO7425', 'RICHARD VALERA', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'DAV2 ↔ PLAS', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUB106'),
(709, NULL, 4175, 'Davao Bottling Plant 2 to GENSAN Distribution Center', 0, 0, '2026-11-16', NULL, '32205508', '2026-11-16', NULL, '14:50:00', 'Davao Bottling Plant 2', 'GENSAN Distribution Center', '46P COKE LITRO', NULL, CURRENT_DATE, 'NJI1511', 'JONATHAN MAMAC', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'GENSAN ↔ DAV2', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUA548'),
(710, NULL, 8496, 'Davao Bottling Plant 2 to GENSAN Distribution Center', 0, 0, '2026-11-16', NULL, '32205509', '2026-11-16', NULL, '16:25:00', 'Davao Bottling Plant 2', 'GENSAN Distribution Center', '46P COKE LITRO', NULL, CURRENT_DATE, 'LAO7425', 'RICHARD VALERA', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'GENSAN ↔ DAV2', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUB106'),
(711, NULL, 8527, 'GENSAN Distribution Center to PLAS Astorga', 0, 0, '2026-11-16', NULL, '32174523', '2026-11-16', '15:52:00', NULL, 'GENSAN Distribution Center', 'PLAS Astorga', '1PALLET', NULL, CURRENT_DATE, 'LAO9202', 'JAMES NACION', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'GENSAN ↔ PLAS', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUA528'),
(712, NULL, 8527, 'PLAS Astorga to Davao Bottling Plant 2', 0, 0, '2026-11-16', 'DR. 0044281', '32204608', '2026-11-16', '19:41:00', '18:09:00', 'PLAS Astorga', 'Davao Bottling Plant 2', '46P COKE LITRO', NULL, CURRENT_DATE, 'LAO9202', 'JAMES NACION', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'DAV2 ↔ PLAS', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUA528'),
(713, NULL, 8527, 'Davao Bottling Plant 2 to GENSAN Distribution Center', 0, 0, '2026-11-16', NULL, '32205520', '2026-11-16', NULL, '20:49:00', 'Davao Bottling Plant 2', 'GENSAN Distribution Center', '46P COKE LITRO', NULL, CURRENT_DATE, 'LAO9202', 'JAMES NACION', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'GENSAN ↔ DAV2', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUA528'),
(714, NULL, 7528, 'GENSAN Distribution Center to PLAS Astorga', 0, 0, '2026-11-16', NULL, '32211073', '2026-11-16', '18:31:00', NULL, 'GENSAN Distribution Center', 'PLAS Astorga', '46P COKE LITRO MTS', NULL, CURRENT_DATE, 'LAS5596', 'JOSE ASPACIO', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'GENSAN ↔ PLAS', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUA551'),
(715, NULL, 7528, 'PLAS Astorga to Davao Bottling Plant 2', 0, 0, '2026-11-16', 'DR. 0044282', '32204609', '2026-11-16', '20:17:00', '20:02:00', 'PLAS Astorga', 'Davao Bottling Plant 2', '46P COKE LITRO MTS', NULL, CURRENT_DATE, 'LAS5596', 'JOSE ASPACIO', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'DAV2 ↔ PLAS', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUA551'),
(716, NULL, 7528, 'Davao Bottling Plant 2 to GENSAN Distribution Center', 0, 0, '2026-11-16', NULL, '32205521', '2026-11-16', NULL, '21:38:00', 'Davao Bottling Plant 2', 'GENSAN Distribution Center', '50P COKE LITRO FULLS', NULL, CURRENT_DATE, 'LAS5596', 'JOSE ASPACIO', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'GENSAN ↔ DAV2', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUA551'),
(717, NULL, 6305, 'GENSAN Distribution Center to PLAS Astorga', 0, 0, '2026-11-16', NULL, '32212537', '2026-11-16', '22:19:00', NULL, 'GENSAN Distribution Center', 'PLAS Astorga', '44P COKE LITRO', NULL, CURRENT_DATE, 'LAQ8291', 'JOVANY MAYORES', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'GENSAN ↔ PLAS', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUA508'),
(718, NULL, 6305, 'PLAS Astorga to Davao Bottling Plant 2', 0, 0, '2026-11-16', 'DR. 0044283', '32204610', '2026-11-16', '23:55:00', '23:30:00', 'PLAS Astorga', 'Davao Bottling Plant 2', '46P COKE LITRO', NULL, CURRENT_DATE, 'LAQ8291', 'JOVANY MAYORES', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'DAV2 ↔ PLAS', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUA508'),
(719, NULL, 6305, 'Davao Bottling Plant 2 to GENSAN Distribution Center', 0, 0, '2026-11-17', NULL, '32205523', '2026-11-17', NULL, '01:05:00', 'Davao Bottling Plant 2', 'GENSAN Distribution Center', '46P COKE LITRO', NULL, CURRENT_DATE, 'LAQ8291', 'JOVANY MAYORES', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'GENSAN ↔ DAV2', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUA508'),
(720, NULL, 65798, 'GENSAN Distribution Center to Davao Bottling Plant 1', 0, 0, '2026-11-17', NULL, '32212535', '2026-11-17', '05:15:00', NULL, 'GENSAN Distribution Center', 'Davao Bottling Plant 1', '36P COKE KASALO MTS', NULL, CURRENT_DATE, 'MAO5280', 'JUSEL CABAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'GENSAN ↔ DAV1', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUA973'),
(721, NULL, 65798, 'Davao Bottling Plant 1 to GENSAN Distribution Center', 0, 0, '2026-11-17', NULL, '32211530', '2026-11-17', NULL, '11:04:00', 'Davao Bottling Plant 1', 'GENSAN Distribution Center', '36P COKE TALL FULLS', NULL, CURRENT_DATE, 'MAO5280', 'JUSEL CABAL', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'GENSAN ↔ DAV1', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUA973'),
(722, NULL, 3513, 'GENSAN Distribution Center to PLAS Astorga', 0, 0, '2026-11-17', NULL, '32218581', '2026-11-17', '15:55:00', NULL, 'GENSAN Distribution Center', 'PLAS Astorga', '50P COKE LITRO MTS', NULL, CURRENT_DATE, 'LAS5593', 'DANDY CABADA', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'GENSAN ↔ PLAS', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUB666'),
(723, NULL, 3513, 'PLAS Astorga to Davao Bottling Plant 2', 0, 0, '2026-11-17', NULL, 'NO LOAD', '2026-11-17', '22:15:00', '22:05:00', 'PLAS Astorga', 'Davao Bottling Plant 2', 'NO LOAD', NULL, CURRENT_DATE, 'LAS5593', 'DANDY CABADA', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'DAV2 ↔ PLAS', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUB666'),
(724, NULL, 7528, 'GENSAN Distribution Center to PLAS Astorga', 0, 0, '2026-11-17', NULL, '32219196', '2026-11-17', '19:52:00', NULL, 'GENSAN Distribution Center', 'PLAS Astorga', '50P COKE LITRO MTS', NULL, CURRENT_DATE, 'LAS5596', 'JOSE ASPACIO', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'GENSAN ↔ PLAS', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUA551'),
(725, NULL, 7528, 'PLAS Astorga to Davao Bottling Plant 2', 0, 0, '2026-11-17', 'DR. 0044292', '32204630', '2026-11-17', '22:16:00', '22:08:00', 'PLAS Astorga', 'Davao Bottling Plant 2', '46P COKE LITRO MTS', NULL, CURRENT_DATE, 'LAS5596', 'JOSE ASPACIO', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'DAV2 ↔ PLAS', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUA551'),
(726, NULL, 3513, 'Davao Bottling Plant 2 to GENSAN Distribution Center', 0, 0, '2026-11-17', 'Underload: 46 pallets available; planned load was 50 pallets.', '32205524', '2026-11-17', NULL, '23:11:00', 'Davao Bottling Plant 2', 'GENSAN Distribution Center', '46P COKE LITRO FULLS', NULL, CURRENT_DATE, 'LAS5593', 'DANDY CABADA', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'GENSAN ↔ DAV2', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUB666'),
(727, NULL, 7528, 'Davao Bottling Plant 2 to PLAS Astorga', 0, 0, '2026-11-17', 'HUSTLING', '32204822', '2026-11-17', '23:29:00', '23:19:00', 'Davao Bottling Plant 2', 'PLAS Astorga', '46P COKE LITRO MTS HUSTLING', NULL, CURRENT_DATE, 'LAS5596', 'JOSE ASPACIO', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'DAV2 ↔ PLAS', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUA551'),
(728, NULL, 7528, 'PLAS Astorga to Davao Bottling Plant 2', 0, 0, '2026-11-18', 'DR. 0044293', '32204631', '2026-11-18', '00:33:00', '00:23:00', 'PLAS Astorga', 'Davao Bottling Plant 2', '46P COKE LITRO MTS', NULL, CURRENT_DATE, 'LAS5596', 'JOSE ASPACIO', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'DAV2 ↔ PLAS', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUA551'),
(729, NULL, 7528, 'Davao Bottling Plant 2 to GENSAN Distribution Center', 0, 0, '2026-11-18', NULL, '32205526', '2026-11-18', NULL, '02:07:00', 'Davao Bottling Plant 2', 'GENSAN Distribution Center', '46P COKE LITRO FULLS', NULL, CURRENT_DATE, 'LAS5596', 'JOSE ASPACIO', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'GENSAN ↔ DAV2', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUA551'),
(730, NULL, 8175, 'GENSAN Distribution Center to Davao Bottling Plant 1', 0, 0, '2026-11-17', NULL, '32212184', '2026-11-17', '22:30:00', NULL, 'GENSAN Distribution Center', 'Davao Bottling Plant 1', '34P COKE TALL', NULL, CURRENT_DATE, 'LAS2007', 'REY MADAMBA', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'GENSAN ↔ DAV1', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUA538'),
(731, NULL, 8175, 'Davao Bottling Plant 1 to GENSAN Distribution Center', 0, 0, '2026-11-18', NULL, '32211538', '2026-11-18', NULL, '03:45:00', 'Davao Bottling Plant 1', 'GENSAN Distribution Center', '12P COKE TALL / 24P ROYAL TALL', NULL, CURRENT_DATE, 'LAS2007', 'REY MADAMBA', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'GENSAN ↔ DAV1', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUA538'),
(732, NULL, 4175, 'GENSAN Distribution Center to PLAS Astorga', 0, 0, '2026-11-18', NULL, '32218550', '2026-11-18', '09:45:00', NULL, 'GENSAN Distribution Center', 'PLAS Astorga', '46P COKE LITRO', NULL, CURRENT_DATE, 'NJI1511', 'JONATHAN MAMAC', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'GENSAN ↔ PLAS', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUA548'),
(733, NULL, 4175, 'PLAS Astorga to Davao Bottling Plant 2', 0, 0, '2026-11-18', 'DR. 0044298', '32204638', '2026-11-18', '11:20:00', '10:35:00', 'PLAS Astorga', 'Davao Bottling Plant 2', '46P COKE LITRO', NULL, CURRENT_DATE, 'NJI1511', 'JONATHAN MAMAC', NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'DAV2 ↔ PLAS', NULL, NULL, NULL, TRUE, NULL, NULL, TRUE, 'pending', NULL, NULL, 'MUA548');

-- Source driver IDs are not trusted because some are malformed or point to a
-- different person. Resolve every imported driver by exact case-insensitive name.
DO $$
DECLARE
    unresolved_drivers text;
BEGIN
    SELECT string_agg(
        format('%s (%s exact matches)', mismatches.driver_name, mismatches.match_count),
        ', '
        ORDER BY mismatches.driver_name
    )
    INTO unresolved_drivers
    FROM (
        SELECT names.driver_name, count(driver.id) AS match_count
        FROM (
            SELECT DISTINCT driver_name
            FROM pg_temp.trip_import_stage
        ) AS names
        LEFT JOIN public.drivers AS driver
            ON upper(btrim(driver.name)) = upper(btrim(names.driver_name))
        GROUP BY names.driver_name
        HAVING count(driver.id) <> 1
    ) AS mismatches;

    IF unresolved_drivers IS NOT NULL THEN
        RAISE EXCEPTION 'Each staged driver name must match exactly one registered driver. Review: %. Import stopped.', unresolved_drivers;
    END IF;

    UPDATE pg_temp.trip_import_stage AS stage
    SET driver_id = driver.id
    FROM public.drivers AS driver
    WHERE upper(btrim(driver.name)) = upper(btrim(stage.driver_name));
END;
$$;

DO $$
BEGIN
    IF (SELECT count(*) FROM pg_temp.trip_import_stage) <> 38 THEN
        RAISE EXCEPTION 'Expected 38 staged rows; import stopped.';
    END IF;

    IF EXISTS (
        SELECT source_id
        FROM pg_temp.trip_import_stage
        GROUP BY source_id
        HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION 'Duplicate source IDs in staging data; import stopped.';
    END IF;

    IF EXISTS (
        SELECT ism_no
        FROM pg_temp.trip_import_stage
        WHERE ism_no IS NULL OR btrim(ism_no) = ''
        GROUP BY ism_no
    ) OR EXISTS (
        SELECT ism_no
        FROM pg_temp.trip_import_stage
        GROUP BY ism_no
        HAVING count(*) > 1
    ) THEN
        RAISE EXCEPTION 'Missing or duplicate ISM numbers in staging data; import stopped.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_temp.trip_import_stage AS stage
        LEFT JOIN public.drivers AS driver ON driver.id = stage.driver_id
        WHERE driver.id IS NULL
          OR upper(btrim(driver.name)) <> upper(btrim(stage.driver_name))
    ) THEN
        RAISE EXCEPTION 'A resolved driver ID does not match its staged driver name; import stopped.';
    END IF;

    IF to_regclass('public.trip_count_counters') IS NULL
       OR NOT EXISTS (
           SELECT 1 FROM public.trip_count_counters WHERE counter_name = 'trips'
       ) THEN
        RAISE EXCEPTION 'Trip-count counter is not installed or initialized; run the trip-count migration first.';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_trigger
        WHERE tgrelid = 'public.trips'::regclass
          AND tgname = 'trips_assign_trip_count'
          AND NOT tgisinternal
    ) THEN
        RAISE EXCEPTION 'Trip-count trigger is not installed; run the trip-count migration first.';
    END IF;
END;
$$;

UPDATE pg_temp.trip_import_stage AS stage
SET skip_reason = CASE
    WHEN EXISTS (
        SELECT 1
        FROM public.trips AS existing
        WHERE upper(btrim(existing.ism_no)) = upper(btrim(stage.ism_no))
          AND existing.shipment_date = stage.shipment_date
          AND upper(btrim(coalesce(existing.driver_name, '')))
              = upper(btrim(coalesce(stage.driver_name, '')))
    )
    THEN 'ISM, shipment date, and driver already exist; skipped as duplicate'
    ELSE 'ISM already exists but the shipment date or driver differs; skipped for review'
END
WHERE EXISTS (
    SELECT 1
    FROM public.trips AS existing
    WHERE upper(btrim(existing.ism_no)) = upper(btrim(stage.ism_no))
);

-- Backfill trailer plates for matching trips from an earlier import that did not
-- populate this field. Do not overwrite an existing plate or update ambiguous ISM
-- conflicts whose shipment date or driver differs.
UPDATE public.trips AS existing
SET trailer_plate_no = stage.trailer_plate_no
FROM pg_temp.trip_import_stage AS stage
WHERE stage.trailer_plate_no IS NOT NULL
  AND btrim(stage.trailer_plate_no) <> ''
  AND upper(btrim(existing.ism_no)) = upper(btrim(stage.ism_no))
  AND existing.shipment_date = stage.shipment_date
  AND upper(btrim(coalesce(existing.driver_name, '')))
      = upper(btrim(coalesce(stage.driver_name, '')))
  AND (existing.trailer_plate_no IS NULL OR btrim(existing.trailer_plate_no) = '');

WITH inserted AS (
    INSERT INTO public.trips (
    vehicle_id,
    driver_id,
    route,
    start_odometer,
    end_odometer,
    trip_date,
    notes,
    ism_no,
    shipment_date,
    time_in,
    time_out,
    origin,
    destination,
    load_details,
    trip_fuel,
    record_date,
    plate_no,
    driver_name,
    created_by,
    updated_by,
    manifest_object_path,
    last_edited_by,
    last_edited_by_email,
    route_id,
    route_number,
    route_pair,
    pallet_capacity,
    truck_route_rate_id,
    truck_route_rate,
    trip_rate_review_required,
    truck_id,
    trailer_id,
    trailer_review_required,
    revenue_status,
    dispatch_movement_id,
    completed_trip_id,
    trailer_plate_no
    )
    SELECT
    stage.vehicle_id,
    stage.driver_id,
    stage.route,
    stage.start_odometer,
    stage.end_odometer,
    stage.trip_date,
    stage.notes,
    stage.ism_no,
    stage.shipment_date,
    stage.time_in,
    stage.time_out,
    stage.origin,
    stage.destination,
    stage.load_details,
    stage.trip_fuel,
    stage.record_date,
    stage.plate_no,
    stage.driver_name,
    stage.created_by,
    stage.updated_by,
    stage.manifest_object_path,
    stage.last_edited_by,
    stage.last_edited_by_email,
    stage.route_id,
    stage.route_number,
    stage.route_pair,
    stage.pallet_capacity,
    stage.truck_route_rate_id,
    stage.truck_route_rate,
    stage.trip_rate_review_required,
    stage.truck_id,
    stage.trailer_id,
    stage.trailer_review_required,
    stage.revenue_status,
    stage.dispatch_movement_id,
    stage.completed_trip_id,
    stage.trailer_plate_no
    FROM pg_temp.trip_import_stage AS stage
    WHERE stage.skip_reason IS NULL
    ORDER BY stage.source_id
    RETURNING id, ism_no
)
UPDATE pg_temp.trip_import_stage AS stage
SET inserted_id = inserted.id
FROM inserted
WHERE inserted.ism_no = stage.ism_no;

DO $$
BEGIN
    IF (
        SELECT count(*)
        FROM pg_temp.trip_import_stage
        WHERE inserted_id IS NOT NULL
    ) <> (
        SELECT count(*)
        FROM pg_temp.trip_import_stage
        WHERE skip_reason IS NULL
    ) THEN
        RAISE EXCEPTION 'Not all non-conflicting trips were inserted; transaction aborted.';
    END IF;
END;
$$;

-- Review all imported and skipped rows, including the existing record for each conflict.
SELECT
    stage.source_id AS source_row_id,
    CASE
        WHEN stage.inserted_id IS NOT NULL THEN 'IMPORTED'
        ELSE 'SKIPPED'
    END AS import_status,
    stage.skip_reason,
    trip.id AS new_trip_id,
    trip.trip_count,
    trip.ism_no,
    trip.shipment_date,
    trip.plate_no,
    trip.trailer_plate_no,
    trip.driver_id,
    trip.driver_name,
    trip.origin,
    trip.destination,
    trip.time_in,
    trip.time_out,
    existing.id AS conflicting_trip_id,
    existing.shipment_date AS conflicting_shipment_date,
    existing.driver_name AS conflicting_driver_name,
    existing.plate_no AS conflicting_plate_no,
    existing.trailer_plate_no AS conflicting_trailer_plate_no,
    existing.origin AS conflicting_origin,
    existing.destination AS conflicting_destination
FROM pg_temp.trip_import_stage AS stage
LEFT JOIN public.trips AS trip ON trip.id = stage.inserted_id
LEFT JOIN public.trips AS existing
    ON stage.skip_reason IS NOT NULL
   AND upper(btrim(existing.ism_no)) = upper(btrim(stage.ism_no))
ORDER BY stage.source_id;

COMMIT;