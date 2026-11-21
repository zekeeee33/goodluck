-- Compare the incoming trip ISM numbers with records already in public.trips.
-- This is read-only and safe to run after the import transaction failed.
WITH incoming (source_row_id, ism_no, shipment_date, driver_name) AS (
    VALUES
        (696, '32160259', DATE '2026-11-14', 'NOLITO SAMARCA'),
        (697, '32211071', DATE '2026-11-14', 'NOLITO SAMARCA'),
        (698, '32198343', DATE '2026-11-15', 'NOLITO SAMARCA'),
        (699, '32213793', DATE '2026-11-16', 'JONATHAN MAMAC'),
        (700, '32204129', DATE '2026-11-16', 'JONATHAN MAMAC'),
        (701, '32174524', DATE '2026-11-16', 'RICHARD VALERA'),
        (702, '32204601', DATE '2026-11-16', 'RICHARD VALERA'),
        (703, '32187675', DATE '2026-11-14', 'NOLITO SAMARCA'),
        (704, '32131119', DATE '2026-11-16', 'JONATHAN MAMAC'),
        (705, '32204809', DATE '2026-11-16', 'RICHARD VALERA'),
        (706, '32160256', DATE '2026-11-16', 'JOVEN JAY BAING'),
        (707, '32204604', DATE '2026-11-16', 'JONATHAN MAMAC'),
        (708, '32204605', DATE '2026-11-16', 'RICHARD VALERA'),
        (709, '32205508', DATE '2026-11-16', 'JONATHAN MAMAC'),
        (710, '32205509', DATE '2026-11-16', 'RICHARD VALERA'),
        (711, '32174523', DATE '2026-11-16', 'JAMES NACION'),
        (712, '32204608', DATE '2026-11-16', 'JAMES NACION'),
        (713, '32205520', DATE '2026-11-16', 'JAMES NACION'),
        (714, '32211073', DATE '2026-11-16', 'JOSE ASPACIO'),
        (715, '32204609', DATE '2026-11-16', 'JOSE ASPACIO'),
        (716, '32205521', DATE '2026-11-16', 'JOSE ASPACIO'),
        (717, '32212537', DATE '2026-11-16', 'JOVANY MAYORES'),
        (718, '32204610', DATE '2026-11-16', 'JOVANY MAYORES'),
        (719, '32205523', DATE '2026-11-17', 'JOVANY MAYORES'),
        (720, '32212535', DATE '2026-11-17', 'JUSEL CABAL'),
        (721, '32211530', DATE '2026-11-17', 'JUSEL CABAL'),
        (722, '32218581', DATE '2026-11-17', 'DANDY CABADA'),
        (723, 'NO LOAD', DATE '2026-11-17', 'DANDY CABADA'),
        (724, '32219196', DATE '2026-11-17', 'JOSE ASPACIO'),
        (725, '32204630', DATE '2026-11-17', 'JOSE ASPACIO'),
        (726, '32205524', DATE '2026-11-17', 'DANDY CABADA'),
        (727, '32204822', DATE '2026-11-17', 'JOSE ASPACIO'),
        (728, '32204631', DATE '2026-11-18', 'JOSE ASPACIO'),
        (729, '32205526', DATE '2026-11-18', 'JOSE ASPACIO'),
        (730, '32212184', DATE '2026-11-17', 'REY MADAMBA'),
        (731, '32211538', DATE '2026-11-18', 'REY MADAMBA'),
        (732, '32218550', DATE '2026-11-18', 'JONATHAN MAMAC'),
        (733, '32204638', DATE '2026-11-18', 'JONATHAN MAMAC')
)
SELECT
    incoming.source_row_id,
    incoming.ism_no AS incoming_ism_no,
    incoming.shipment_date AS incoming_shipment_date,
    incoming.driver_name AS incoming_driver_name,
    existing.id AS existing_trip_id,
    existing.ism_no AS existing_ism_no,
    existing.shipment_date AS existing_shipment_date,
    existing.driver_name AS existing_driver_name,
    existing.plate_no AS existing_plate_no,
    existing.origin AS existing_origin,
    existing.destination AS existing_destination
FROM incoming
JOIN public.trips AS existing
    ON upper(btrim(existing.ism_no)) = upper(btrim(incoming.ism_no))
ORDER BY incoming.source_row_id, existing.id;
