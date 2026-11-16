from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

TRIP_REPORT_FIELDS = (
    ("trip_count", "Trip Count"),
    ("trip_date", "Trip Date"),
    ("driver_name", "Driver Name"),
    ("truck_plate", "Truck / Vehicle"),
    ("trailer_plate", "Trailer"),
    ("origin", "Origin"),
    ("destination", "Destination"),
    ("shipment_date", "Shipment Date"),
    ("ism_no", "ISM Number"),
    ("time_in", "Time In"),
    ("time_out", "Time Out"),
    ("load_details", "Load Details"),
)


TRIP_REPORT_GROUPINGS = {
    "all": "All Trips",
    "driver": "By Driver",
    "origin": "By Origin",
    "destination": "By Destination",
    "truck": "By Truck",
    "trailer": "By Trailer",
}


def _trip_group_key(trip: dict[str, Any], group_by: str) -> tuple[str, str]:
    if group_by == "driver":
        label = " ".join(str(trip.get("driver_name") or "").split())
        return ("name", label.casefold() or "unassigned")
    if group_by == "origin":
        label = str(trip.get("origin") or "").strip() or "Unknown origin"
        return ("value", label.casefold())
    if group_by == "destination":
        label = str(trip.get("destination") or "").strip() or "Unknown destination"
        return ("value", label.casefold())
    if group_by == "truck":
        identity = trip.get("truck_id")
        label = str(trip.get("truck_plate") or "").strip() or "Unknown truck"
        return (
            ("id", str(identity)) if identity is not None
            else ("plate", label.casefold())
        )
    if group_by == "trailer":
        identity = trip.get("trailer_id")
        label = str(trip.get("trailer_plate") or "").strip() or "No trailer"
        return (
            ("id", str(identity)) if identity is not None
            else ("plate", label.casefold())
        )
    raise ValueError(f"Unsupported trip report grouping: {group_by}")


def _trip_group_label(trip: dict[str, Any], group_by: str) -> str:
    if group_by == "driver":
        return " ".join(str(trip.get("driver_name") or "").split()) or "Unassigned driver"
    if group_by == "origin":
        return str(trip.get("origin") or "").strip() or "Unknown origin"
    if group_by == "destination":
        return str(trip.get("destination") or "").strip() or "Unknown destination"
    if group_by == "truck":
        return str(trip.get("truck_plate") or "").strip() or "Unknown truck"
    if group_by == "trailer":
        return str(trip.get("trailer_plate") or "").strip() or "No trailer"
    raise ValueError(f"Unsupported trip report grouping: {group_by}")


def order_trip_records(
    trips: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    indexed_trips = list(enumerate(trips))

    def sort_key(item: tuple[int, dict[str, Any]]) -> tuple[bool, int, int]:
        index, trip = item
        try:
            trip_count = int(trip["trip_count"])
        except (KeyError, TypeError, ValueError):
            return (True, index, index)
        return (False, trip_count, index)

    return [trip for _, trip in sorted(indexed_trips, key=sort_key)]


def group_trip_records(
    trips: list[dict[str, Any]],
    group_by: str,
) -> list[tuple[str, list[dict[str, Any]]]]:
    trips = order_trip_records(trips)
    if group_by == "all":
        return [(TRIP_REPORT_GROUPINGS[group_by], trips)]

    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    labels: dict[tuple[str, str], str] = {}
    for trip in trips:
        key = _trip_group_key(trip, group_by)
        groups[key].append(trip)
        label = _trip_group_label(trip, group_by)
        placeholder = "Unassigned driver" if group_by == "driver" else ""
        if key not in labels or (
            labels[key] == placeholder and label != placeholder
        ):
            labels[key] = label

    label_counts: dict[str, int] = defaultdict(int)
    for label in labels.values():
        label_counts[label.casefold()] += 1

    result = []
    for key in sorted(groups, key=lambda group_key: (
        labels[group_key].casefold(), group_key
    )):
        label = labels[key]
        if label_counts[label.casefold()] > 1 and key[0] == "id":
            label = f"{label} (ID: {key[1]})"
        result.append((label, order_trip_records(groups[key])))
    return result


def group_trip_records_by_driver(
    trips: list[dict[str, Any]],
) -> list[tuple[str, list[dict[str, Any]]]]:
    return group_trip_records(trips, "driver")


def completed_trip_records(
    trips: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    unique_trips: dict[str, dict[str, Any]] = {}
    for index, trip in enumerate(trips):
        if str(trip.get("status") or "").strip().casefold() != "completed":
            continue
        trip_id = trip.get("id")
        identity = f"id:{trip_id}" if trip_id is not None else f"row:{index}"
        unique_trips.setdefault(identity, trip)
    return order_trip_records(list(unique_trips.values()))


def _route_identifier(trip: dict[str, Any]) -> str:
    route_number = trip.get("route_number")
    return str(route_number).strip() if route_number not in (None, "") else ""


def group_trip_records_by_route(
    trips: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    trips = order_trip_records(trips)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    labels: dict[tuple[str, str], tuple[str, str, str]] = {}
    for trip in trips:
        origin = " ".join(str(trip.get("origin") or "").split())
        destination = " ".join(str(trip.get("destination") or "").split())
        route_number = trip.get("route_number")
        if route_number not in (None, ""):
            key = ("route_number", str(route_number).strip().casefold())
            identifier = str(route_number)
        else:
            normalized_origin = " ".join(str(origin or "Unknown origin").split()).casefold()
            normalized_destination = " ".join(str(destination or "Unknown destination").split()).casefold()
            key = (
                "origin_destination",
                f"{normalized_origin} -> {normalized_destination}",
            )
            identifier = ""

        groups[key].append(trip)
        labels.setdefault(
            key,
            (
                identifier,
                origin or "Unknown origin",
                destination or "Unknown destination",
            ),
        )

    ordered_keys = sorted(
        groups,
        key=lambda key: (
            labels[key][1].casefold(),
            labels[key][2].casefold(),
            key[1].casefold(),
        ),
    )
    result = []
    for key in ordered_keys:
        identifier, origin, destination = labels[key]
        route_number = next(
            (
                trip.get("route_number")
                for trip in groups[key]
                if trip.get("route_number") not in (None, "")
            ),
            None,
        )
        if route_number not in (None, ""):
            identifier = str(route_number)
        result.append({
            "identifier": identifier,
            "label": f"Route {identifier}" if identifier else "Route —",
            "origin": origin or "Unknown origin",
            "destination": destination or "Unknown destination",
            "trips": groups[key],
        })
    return result


def summarize_trip_records(trips: list[dict[str, Any]]) -> dict[str, Any]:
    total_distance = Decimal("0")
    total_revenue = Decimal("0")
    distance_trip_count = 0
    revenue_trip_count = 0
    for trip in trips:
        distance = trip.get("distance")
        if distance is not None:
            total_distance += Decimal(str(distance))
            distance_trip_count += 1
        revenue = trip.get("trip_revenue")
        if revenue is not None:
            total_revenue += Decimal(str(revenue))
            revenue_trip_count += 1
    average_revenue = (
        total_revenue / revenue_trip_count if revenue_trip_count else None
    )
    return {
        "total_trips": len(trips),
        "total_distance": total_distance,
        "distance_trip_count": distance_trip_count,
        "total_revenue": total_revenue,
        "revenue_trip_count": revenue_trip_count,
        "average_revenue_per_trip": average_revenue,
    }
