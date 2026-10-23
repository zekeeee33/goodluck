#!/usr/bin/env python3
"""Good Luck Forwarding Systems Inc. Fleet Management System backed by Supabase."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit, urlunsplit

from dotenv import load_dotenv
from supabase import Client, create_client

from manifest_ocr import canonical_warehouse_code

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))


def _supabase_project_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise FleetManagementError(
            "SUPABASE_URL must be the project URL, such as "
            "https://your-project-ref.supabase.co."
        )
    path = parsed.path.rstrip("/")
    if path.endswith("/rest/v1"):
        path = path[:-len("/rest/v1")]
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


class FleetManagementError(RuntimeError):
    """Raised when a fleet action or Supabase request fails."""


class TripRateValidationError(FleetManagementError):
    """Raised when a trip cannot be matched to a configured hauling rate."""


class FleetManager:
    """Fleet data access through the Supabase PostgREST API."""

    def __init__(
        self,
        url: Optional[str] = None,
        key: Optional[str] = None,
        client: Optional[Client] = None,
    ):
        self.client = client
        if self.client is None:
            project_url = url or os.environ.get("SUPABASE_URL")
            api_key = key or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
            if not project_url or not api_key:
                raise FleetManagementError(
                    "Supabase is not configured. Set SUPABASE_URL and "
                    "SUPABASE_SERVICE_ROLE_KEY in your environment or .env file."
                )
            try:
                self.client = create_client(_supabase_project_url(project_url), api_key)
            except Exception as exc:
                raise FleetManagementError(f"Could not initialize Supabase: {exc}") from exc

    def _execute(self, query: Any) -> Any:
        try:
            return query.execute()
        except Exception as exc:
            error_details = []
            pending = [exc]
            seen = set()
            while pending:
                current = pending.pop()
                if id(current) in seen:
                    continue
                seen.add(id(current))
                error_details.append(str(current).lower())
                error_details.extend(str(arg).lower() for arg in current.args)
                for related in (current.__cause__, current.__context__):
                    if related is not None:
                        pending.append(related)
            combined_error = " ".join(error_details)
            if "getaddrinfo failed" in combined_error or "11001" in combined_error:
                project_url = os.environ.get("SUPABASE_URL", "")
                hostname = urlsplit(project_url).hostname
                host_detail = f" ({hostname})" if hostname else ""
                raise FleetManagementError(
                    "Could not resolve the Supabase server"
                    f"{host_detail}. Verify SUPABASE_URL in .env matches the "
                    "Project URL in Supabase Settings > API, check your internet "
                    "or VPN/DNS settings, and restart the app."
                ) from exc
            if any(
                marker in combined_error
                for marker in (
                    "tire_monitoring",
                    "tire_monitoring_sheet",
                    "get_tire_monitoring_summary",
                    "replace_tire_monitoring",
                    "remove_tire_monitoring",
                )
            ) and any(
                marker in combined_error
                for marker in ("does not exist", "schema cache", "could not find the function")
            ):
                raise FleetManagementError(
                    "Tire Monitoring is not installed in Supabase. Apply "
                    "supabase_tire_monitoring_migration.sql after the base schema "
                    "and truck/trailer migrations, then refresh the app."
                ) from exc
            if "column trips.shipment_date does not exist" in combined_error:
                raise FleetManagementError(
                    "The Supabase trips table needs its shipment fields. Run "
                    "supabase_trips_migration.sql in the Supabase SQL Editor, "
                    "then refresh the app."
                ) from exc
            if "column fuel_logs.trip_id does not exist" in combined_error:
                raise FleetManagementError(
                    "Fuel logs are not linked to trips in Supabase. Run "
                    "supabase_fuel_allocation_migration.sql in the Supabase SQL "
                    "Editor, then refresh the app."
                ) from exc
            if "function hashtextext(text) does not exist" in combined_error:
                raise FleetManagementError(
                    "The Supabase payroll finalization function is outdated. Run "
                    "the updated supabase_payroll_migration.sql in the Supabase "
                    "SQL Editor, then retry payroll finalization."
                ) from exc
            if any(
                marker in combined_error
                for marker in (
                    "revenue_dashboard",
                    "set_trip_revenue_status",
                    "add_revenue_adjustment",
                    "revenue_status",
                    "revenue_adjustments",
                    "trip_revenue_status_history",
                )
            ) and any(
                marker in combined_error
                for marker in ("does not exist", "schema cache", "could not find the function")
            ):
                raise FleetManagementError(
                    "The Revenue dashboard schema is not installed. Run "
                    "supabase_revenue_dashboard_migration.sql after the route "
                    "and trailer migrations, then refresh the app."
                ) from exc
            missing_edit_history = (
                "column trips.last_edited_by does not exist" in combined_error
                or "column trips.last_edited_by_email does not exist" in combined_error
                or (
                    "trip_edit_history" in combined_error
                    and (
                        "does not exist" in combined_error
                        or "schema cache" in combined_error
                    )
                )
            )
            if missing_edit_history:
                raise FleetManagementError(
                    "Trip edit history is not installed. Run "
                    "supabase_dispatcher_ownership_migration.sql in the Supabase "
                    "SQL Editor, then refresh the app."
                ) from exc
            if "payroll_periods" in combined_error and (
                "does not exist" in combined_error or "schema cache" in combined_error
            ):
                raise FleetManagementError(
                    "Payroll tables are not installed. Run "
                    "supabase_payroll_migration.sql in the Supabase SQL Editor, "
                    "then refresh the app."
                ) from exc
            if "notifications" in combined_error and (
                "does not exist" in combined_error or "schema cache" in combined_error
            ):
                raise FleetManagementError(
                    "Admin notifications are not installed. Run "
                    "supabase_notifications_migration.sql in the Supabase SQL "
                    "Editor, then refresh the app."
                ) from exc
            if any(
                marker in combined_error
                for marker in (
                    "truck_routes",
                    "truck_route_rates",
                    "route_number",
                    "trips.route_id",
                    "trips.truck_route_rate",
                    "truck_route_rate_id",
                    "trip_rate_review_required",
                    "route_pair",
                    "pallet_capacity",
                    "trailer_id",
                    "trailer_review_required",
                )
            ):
                raise FleetManagementError(
                    "Trip route, rate, or trailer data is not installed. Run "
                    "supabase_route_trip_rate_migration.sql and "
                    "supabase_truck_trailer_migration.sql in the Supabase SQL "
                    "Editor, then refresh the app."
                ) from exc
            raise FleetManagementError(f"Supabase request failed: {exc}") from exc

    def _insert(self, table: str, values: Dict[str, Any]) -> Dict[str, Any]:
        response = self._execute(
            self.client.table(table).insert(values).select("*")
        )
        rows = response.data or []
        if not rows:
            raise FleetManagementError(f"Supabase did not return the inserted {table} record")
        return dict(rows[0])

    def _select_all(
        self,
        table: str,
        select: str,
        order: Optional[tuple[str, str]] = None,
        filters: Optional[
            List[tuple[str, Any] | tuple[str, str, Any]]
        ] = None,
    ) -> List[Dict[str, Any]]:
        page_size = 1000
        offset = 0
        result: List[Dict[str, Any]] = []
        while True:
            query = self.client.table(table).select(select)
            for filter_spec in filters or []:
                if len(filter_spec) == 2:
                    column, value = filter_spec
                    query = query.eq(column, value)
                else:
                    operator, column, value = filter_spec
                    query = getattr(query, operator)(column, value)
            if order:
                column, direction = order
                query = query.order(column, desc=direction == "desc")
            response = self._execute(query.range(offset, offset + page_size - 1))
            page = response.data or []
            result.extend(dict(row) for row in page)
            if len(page) < page_size:
                return result
            offset += page_size

    def _select_by_values(
        self,
        table: str,
        select: str,
        column: str,
        values: List[Any],
        filters: Optional[List[tuple[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        unique_values = list(dict.fromkeys(value for value in values if value is not None))
        result: List[Dict[str, Any]] = []
        for start in range(0, len(unique_values), 500):
            value_batch = unique_values[start : start + 500]
            offset = 0
            while True:
                query = self.client.table(table).select(select).in_(column, value_batch)
                for filter_column, filter_value in filters or []:
                    query = query.eq(filter_column, filter_value)
                response = self._execute(query.range(offset, offset + 999))
                page = response.data or []
                result.extend(dict(row) for row in page)
                if len(page) < 1000:
                    break
                offset += 1000
        return result

    def _list(
        self,
        table: str,
        select: str = "*",
        order: Optional[tuple[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        return self._select_all(table, select, order)

    def _get(self, table: str, record_id: int) -> Dict[str, Any]:
        response = self._execute(
            self.client.table(table).select("*").eq("id", record_id).limit(1)
        )
        rows = response.data or []
        if not rows:
            raise FleetManagementError(f"{table.rstrip('s').capitalize()} {record_id} not found")
        return dict(rows[0])

    def _delete(self, table: str, record_id: int) -> None:
        self._execute(self.client.table(table).delete().eq("id", record_id))

    def _related_list(
        self,
        table: str,
        select: str,
        order: tuple[str, str],
        owner_id: Optional[str] = None,
        filters: Optional[
            List[tuple[str, Any] | tuple[str, str, Any]]
        ] = None,
    ) -> List[Dict[str, Any]]:
        rows = []
        query_filters = list(filters or [])
        if owner_id is not None:
            query_filters.append(("created_by", owner_id))
        for row in self._select_all(table, select, order, query_filters):
            driver = row.pop("driver", None)
            vehicle = row.pop("truck", None) if table == "trips" else row.pop("vehicle", None)
            trailer = row.pop("trailer", None)
            if isinstance(driver, dict):
                row["driver_name"] = driver.get("name")
            if isinstance(vehicle, dict):
                row.update(
                    {
                        key: value
                        for key, value in vehicle.items()
                        if key in ("plate_number", "make", "model")
                    }
                )
            elif table == "trips" and row.get("plate_no"):
                row["plate_number"] = row["plate_no"]
            if isinstance(vehicle, dict):
                row["truck_plate_number"] = vehicle.get("plate_number")
            if isinstance(trailer, dict):
                row["trailer_plate_number"] = trailer.get("plate_number")
                row["trailer_type"] = trailer.get("trailer_type")
                row["trailer_status"] = trailer.get("status")
            rows.append(row)
        return rows

    def _exists(self, table: str, record_id: int) -> bool:
        response = self._execute(
            self.client.table(table).select("id").eq("id", record_id).limit(1)
        )
        return bool(response.data)

    @staticmethod
    def _normalize_owner(value: Optional[Any]) -> Optional[str]:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @classmethod
    def _matches_owner(cls, row: Dict[str, Any], user_id: Optional[str]) -> bool:
        if user_id is None:
            return True
        owner_value = cls._normalize_owner(
            row.get("created_by")
            or row.get("dispatcher_id")
            or row.get("user_id")
        )
        return owner_value == cls._normalize_owner(user_id)

    @classmethod
    def _filter_owned_rows(cls, rows: List[Dict[str, Any]], user_id: Optional[str]) -> List[Dict[str, Any]]:
        if user_id is None:
            return rows
        return [row for row in rows if cls._matches_owner(row, user_id)]

    def add_vehicle(
        self,
        plate_number: str,
        make: str,
        model: str,
        year: int,
        color: Optional[str] = None,
        status: str = "available",
        odometer: int = 0,
        registration_expiry: Optional[str] = None,
        insurance_expiry: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not plate_number or not make or not model:
            raise FleetManagementError("plate_number, make, and model are required")
        if year < 1900 or year > datetime.now().year + 2:
            raise FleetManagementError("vehicle year is out of range")
        if odometer < 0:
            raise FleetManagementError("odometer cannot be negative")
        if status not in {"active", "available", "assigned", "inactive", "maintenance"}:
            raise FleetManagementError("Truck status is invalid.")
        return self._insert(
            "vehicles",
            {
                "plate_number": plate_number.strip(),
                "make": make.strip(),
                "model": model.strip(),
                "year": year,
                "color": color.strip() if color else None,
                "status": status.strip(),
                "odometer": odometer,
                "registration_expiry": registration_expiry,
                "insurance_expiry": insurance_expiry,
            },
        )

    def get_vehicle(self, vehicle_id: int) -> Dict[str, Any]:
        return self._get("vehicles", vehicle_id)

    def update_vehicle(self, vehicle_id: int, values: Dict[str, Any]) -> Dict[str, Any]:
        allowed = {
            "plate_number", "make", "model", "year", "color", "status",
            "odometer", "registration_expiry", "insurance_expiry",
        }
        if not values or set(values) - allowed:
            raise FleetManagementError("The truck contains unsupported fields.")
        if not str(values.get("plate_number") or "").strip():
            raise FleetManagementError("Truck plate number is required.")
        if int(values.get("year") or 0) < 1900:
            raise FleetManagementError("Truck year is out of range.")
        if int(values.get("odometer") or 0) < 0:
            raise FleetManagementError("Truck odometer cannot be negative.")
        if values.get("status") not in {
            "active", "available", "assigned", "inactive", "maintenance",
        }:
            raise FleetManagementError("Truck status is invalid.")
        response = self._execute(
            self.client.table("vehicles")
            .update(values)
            .eq("id", vehicle_id)
            .select("*")
        )
        if not response.data:
            raise FleetManagementError(f"Truck {vehicle_id} not found")
        return dict(response.data[0])

    def add_trailer(
        self,
        plate_number: str,
        pallet_capacity: Optional[int] = None,
        trailer_type: Optional[str] = None,
        status: str = "active",
        remarks: Optional[str] = None,
        year_model: Optional[int] = None,
        make_model: Optional[str] = None,
        mv_file_no: Optional[str] = None,
        engine_no: Optional[str] = None,
        chassis_no: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not plate_number or not plate_number.strip():
            raise FleetManagementError("Trailer plate number is required.")
        if pallet_capacity is not None and pallet_capacity <= 0:
            raise FleetManagementError("Trailer pallet capacity must be greater than zero.")
        if year_model is not None and year_model < 1900:
            raise FleetManagementError("Trailer year must be 1900 or later.")
        if status not in {"active", "inactive", "maintenance"}:
            raise FleetManagementError("Trailer status is invalid.")
        return self._insert(
            "trailers",
            {
                "plate_number": plate_number.strip(),
                "pallet_capacity": int(pallet_capacity) if pallet_capacity is not None else None,
                "capacity_review_required": pallet_capacity is None,
                "year_model": year_model,
                "make_model": make_model.strip() if make_model else None,
                "mv_file_no": mv_file_no.strip() if mv_file_no else None,
                "engine_no": engine_no.strip() if engine_no else None,
                "chassis_no": chassis_no.strip() if chassis_no else None,
                "trailer_type": trailer_type.strip() if trailer_type else None,
                "status": status,
                "remarks": remarks.strip() if remarks else None,
            },
        )

    def update_trailer(self, trailer_id: int, values: Dict[str, Any]) -> Dict[str, Any]:
        allowed = {
            "plate_number", "pallet_capacity", "year_model", "make_model",
            "mv_file_no", "engine_no", "chassis_no", "trailer_type", "status",
            "remarks",
        }
        if not values or set(values) - allowed:
            raise FleetManagementError("The trailer contains unsupported fields.")
        if not str(values.get("plate_number") or "").strip():
            raise FleetManagementError("Trailer plate number is required.")
        raw_capacity = values.get("pallet_capacity")
        try:
            capacity = int(raw_capacity) if raw_capacity not in (None, "") else None
            if isinstance(raw_capacity, float) and not raw_capacity.is_integer():
                raise ValueError
        except (TypeError, ValueError) as exc:
            raise FleetManagementError("Trailer pallet capacity must be a whole number.") from exc
        if capacity is not None and capacity <= 0:
            raise FleetManagementError("Trailer pallet capacity must be greater than zero.")
        year_model = values.get("year_model")
        if year_model in ("", None):
            year_model = None
        else:
            try:
                parsed_year = int(year_model)
                if isinstance(year_model, float) and not year_model.is_integer():
                    raise ValueError
            except (TypeError, ValueError) as exc:
                raise FleetManagementError("Trailer year must be a whole number.") from exc
            if parsed_year < 1900:
                raise FleetManagementError("Trailer year must be 1900 or later.")
            year_model = parsed_year
        if values.get("status") not in {"active", "inactive", "maintenance"}:
            raise FleetManagementError("Trailer status is invalid.")
        response = self._execute(
            self.client.table("trailers")
            .update(
                {
                    **values,
                    "pallet_capacity": capacity,
                    "capacity_review_required": capacity is None,
                    "year_model": year_model,
                }
            )
            .eq("id", trailer_id)
            .select("*")
        )
        if not response.data:
            raise FleetManagementError(f"Trailer {trailer_id} not found")
        return dict(response.data[0])

    def add_driver(
        self,
        name: str,
        license_number: str,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        status: str = "active",
    ) -> Dict[str, Any]:
        if not name or not license_number:
            raise FleetManagementError("name and license_number are required")
        return self._insert(
            "drivers",
            {
                "name": name.strip(),
                "license_number": license_number.strip(),
                "phone": phone,
                "email": email,
                "status": status.strip(),
            },
        )

    def get_driver(self, driver_id: int) -> Dict[str, Any]:
        return self._get("drivers", driver_id)

    def list_vehicles(self) -> List[Dict[str, Any]]:
        return self._list("vehicles", order=("plate_number", "asc"))

    def list_drivers(self) -> List[Dict[str, Any]]:
        return self._list("drivers", order=("name", "asc"))

    def delete_vehicle(self, vehicle_id: int) -> None:
        self.get_vehicle(vehicle_id)
        assigned = self._select_all(
            "trips", "id", filters=[("truck_id", vehicle_id)]
        )
        if not assigned:
            assigned = self._select_all(
                "trips", "id", filters=[("vehicle_id", vehicle_id)]
            )
        if assigned:
            raise FleetManagementError(
                "This truck is present in trip history. Mark it inactive instead of deleting it."
            )
        self._delete("vehicles", vehicle_id)

    def delete_driver(self, driver_id: int) -> None:
        self._delete("drivers", driver_id)

    def assign_vehicle(
        self,
        driver_id: int,
        vehicle_id: int,
        assigned_date: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self._exists("drivers", driver_id):
            raise FleetManagementError(f"Driver {driver_id} not found")
        if not self._exists("vehicles", vehicle_id):
            raise FleetManagementError(f"Vehicle {vehicle_id} not found")
        self._execute(
            self.client.table("vehicles").update({"status": "assigned"}).eq("id", vehicle_id)
        )
        return self._insert(
            "assignments",
            {
                "driver_id": driver_id,
                "vehicle_id": vehicle_id,
                "assigned_date": assigned_date or datetime.now().date().isoformat(),
                "notes": notes,
            },
        )

    def get_assignment(self, assignment_id: int) -> Dict[str, Any]:
        response = self._execute(
            self.client.table("assignments")
            .select("*,driver:drivers(name),vehicle:vehicles(plate_number,make,model)")
            .eq("id", assignment_id)
            .limit(1)
        )
        if not response.data:
            raise FleetManagementError(f"Assignment {assignment_id} not found")
        return self._flatten_assignment(dict(response.data[0]))

    @staticmethod
    def _flatten_assignment(row: Dict[str, Any]) -> Dict[str, Any]:
        driver = row.pop("driver", None)
        vehicle = row.pop("vehicle", None)
        if isinstance(driver, dict):
            row["driver_name"] = driver.get("name")
        if isinstance(vehicle, dict):
            row.update(
                {
                    key: vehicle.get(key)
                    for key in ("plate_number", "make", "model")
                }
            )
        elif row.get("plate_no"):
            row["plate_number"] = row["plate_no"]
        return row

    def list_assignments(self) -> List[Dict[str, Any]]:
        rows = self._related_list(
            "assignments",
            "*,driver:drivers(name),vehicle:vehicles(plate_number,make,model)",
            ("assigned_date", "desc"),
        )
        return [self._flatten_assignment(row) for row in rows]

    def delete_assignment(self, assignment_id: int) -> None:
        self._delete("assignments", assignment_id)

    def add_maintenance(
        self,
        vehicle_id: int,
        service_type: str,
        description: Optional[str],
        cost: float,
        performed_on: Optional[str] = None,
        created_by: Optional[Any] = None,
    ) -> Dict[str, Any]:
        if not self._exists("vehicles", vehicle_id):
            raise FleetManagementError(f"Vehicle {vehicle_id} not found")
        if not service_type:
            raise FleetManagementError("service_type is required")
        owner = self._normalize_owner(created_by)
        payload = {
            "vehicle_id": vehicle_id,
            "service_type": service_type.strip(),
            "description": description,
            "cost": float(cost),
            "performed_on": performed_on or datetime.now().date().isoformat(),
        }
        if owner is not None:
            payload["created_by"] = owner
        return self._insert("maintenance", payload)

    def get_maintenance(self, maintenance_id: int, user_id: Optional[str] = None) -> Dict[str, Any]:
        row = self._get("maintenance", maintenance_id)
        if user_id is not None and not self._matches_owner(row, user_id):
            raise FleetManagementError(f"You do not have access to maintenance record {maintenance_id}")
        return row

    def list_maintenance(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = self._related_list(
            "maintenance",
            "*,vehicle:vehicles(plate_number)",
            ("performed_on", "desc"),
            owner_id=user_id,
        )
        return rows if user_id is None else self._filter_owned_rows(rows, user_id)

    def add_fuel(
        self,
        vehicle_id: int,
        fuel_type: str = "diesel",
        quantity: Optional[float] = None,
        price_per_liter: Optional[float] = None,
        total_cost: Optional[float] = None,
        logged_on: Optional[str] = None,
        created_by: Optional[Any] = None,
        trip_id: Optional[int] = None,
        fuel_allocation: Optional[float] = None,
        actual_expense: Optional[float] = None,
        remarks: Optional[str] = None,
        invoice_object_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self._exists("vehicles", vehicle_id):
            raise FleetManagementError(f"Vehicle {vehicle_id} not found")
        owner = self._normalize_owner(created_by)

        # Prevent duplicate fuel records when the user submits the same trip form more than once.
        if trip_id is not None:
            existing_fuel_records = self._select_all("fuel_logs", "*", filters=[("trip_id", trip_id)])
            if existing_fuel_records:
                existing_record = existing_fuel_records[0]
                update_payload: Dict[str, Any] = {}
                if vehicle_id is not None:
                    update_payload["vehicle_id"] = vehicle_id
                if fuel_type:
                    update_payload["fuel_type"] = fuel_type.strip()
                if quantity is not None:
                    update_payload["quantity"] = float(quantity)
                if price_per_liter is not None:
                    update_payload["price_per_liter"] = float(price_per_liter)
                if total_cost is not None:
                    update_payload["total_cost"] = float(total_cost)
                elif actual_expense is not None and "total_cost" not in update_payload:
                    update_payload["total_cost"] = float(actual_expense)
                if fuel_allocation is not None:
                    update_payload["fuel_allocation"] = float(fuel_allocation)
                if actual_expense is not None:
                    update_payload["actual_expense"] = float(actual_expense)
                if remarks is not None:
                    update_payload["remarks"] = remarks.strip() if remarks else None
                if invoice_object_path is not None:
                    update_payload["invoice_object_path"] = invoice_object_path
                if logged_on:
                    update_payload["logged_on"] = logged_on

                response = self._execute(
                    self.client.table("fuel_logs")
                    .update(update_payload)
                    .eq("id", existing_record["id"])
                    .select("*")
                )
                return dict(response.data[0]) if response.data else existing_record

        has_volume = quantity is not None and price_per_liter is not None
        has_allocation_or_expense = fuel_allocation is not None or actual_expense is not None
        is_trip_fuel = trip_id is not None

        if not has_volume and not has_allocation_or_expense and not is_trip_fuel:
            raise FleetManagementError("Provide either quantity and price_per_liter or fuel allocation and expense.")
        if has_volume:
            if float(quantity) <= 0 or float(price_per_liter) <= 0:
                raise FleetManagementError("quantity and price_per_liter must be positive")
            calculated_cost = float(total_cost) if total_cost is not None else float(quantity) * float(price_per_liter)
        elif actual_expense is not None:
            calculated_cost = float(actual_expense) if total_cost is None else float(total_cost)
        else:
            calculated_cost = float(total_cost) if total_cost is not None else None

        payload: Dict[str, Any] = {
            "vehicle_id": vehicle_id,
            "fuel_type": fuel_type.strip() if fuel_type else "diesel",
            "quantity": float(quantity) if quantity is not None else None,
            "price_per_liter": float(price_per_liter) if price_per_liter is not None else None,
            "total_cost": calculated_cost,
            "logged_on": logged_on or datetime.now().date().isoformat(),
            "trip_id": trip_id,
            "fuel_allocation": float(fuel_allocation) if fuel_allocation is not None else None,
            "actual_expense": float(actual_expense) if actual_expense is not None else None,
            "remarks": remarks.strip() if remarks else None,
            "invoice_object_path": invoice_object_path,
        }
        if owner is not None:
            payload["created_by"] = owner
        return self._insert("fuel_logs", payload)

    def update_fuel(
        self,
        fuel_id: int,
        values: Dict[str, Any],
        edited_by: str,
        editor_email: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        current = self.get_fuel(fuel_id, user_id)
        allowed = {
            "vehicle_id",
            "fuel_type",
            "quantity",
            "price_per_liter",
            "total_cost",
            "logged_on",
            "fuel_allocation",
            "actual_expense",
            "remarks",
            "invoice_object_path",
        }
        filtered = {k: v for k, v in values.items() if k in allowed}
        if "quantity" in filtered and filtered["quantity"] is not None:
            filtered["quantity"] = float(filtered["quantity"])
        if "price_per_liter" in filtered and filtered["price_per_liter"] is not None:
            filtered["price_per_liter"] = float(filtered["price_per_liter"])
        if "fuel_allocation" in filtered and filtered["fuel_allocation"] is not None:
            filtered["fuel_allocation"] = float(filtered["fuel_allocation"])
        if "actual_expense" in filtered and filtered["actual_expense"] is not None:
            filtered["actual_expense"] = float(filtered["actual_expense"])
            if "total_cost" not in filtered:
                filtered["total_cost"] = filtered["actual_expense"]
        if "total_cost" in filtered and filtered["total_cost"] is not None:
            filtered["total_cost"] = float(filtered["total_cost"])

        update_payload = {
            **filtered,
            "last_edited_by": edited_by,
            "last_edited_by_email": editor_email,
        }
        query = (
            self.client.table("fuel_logs")
            .update(update_payload)
            .eq("id", fuel_id)
        )
        if user_id is not None:
            query = query.eq("created_by", user_id)
        response = self._execute(query.select("*"))
        if not response.data:
            raise FleetManagementError(f"Fuel log {fuel_id} was not found or is not accessible")
        updated_row = dict(response.data[0])

        old_snapshot = {
            k: v for k, v in current.items()
            if k not in ("created_by", "last_edited_by", "last_edited_by_email")
        }
        new_snapshot = {
            k: v for k, v in updated_row.items()
            if k not in ("created_by", "last_edited_by", "last_edited_by_email")
        }
        try:
            self._insert(
                "fuel_edit_history",
                {
                    "fuel_id": fuel_id,
                    "edited_by": edited_by,
                    "edited_by_email": editor_email,
                    "old_values": old_snapshot,
                    "new_values": new_snapshot,
                },
            )
        except Exception:
            pass
        return updated_row

    def list_fuel_edit_history(
        self, fuel_id: int, user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        self.get_fuel(fuel_id, user_id)
        response = self._execute(
            self.client.table("fuel_edit_history")
            .select("id,fuel_id,edited_by,edited_by_email,edited_at,old_values,new_values")
            .eq("fuel_id", fuel_id)
            .order("edited_at", desc=True)
        )
        return [dict(row) for row in (response.data or [])]

    def get_fuel(self, fuel_id: int, user_id: Optional[str] = None) -> Dict[str, Any]:
        row = self._get("fuel_logs", fuel_id)
        if user_id is not None and not self._matches_owner(row, user_id):
            raise FleetManagementError(f"You do not have access to fuel log {fuel_id}")
        return row

    def set_fuel_invoice_path(
        self, fuel_id: int, object_path: str, user_id: Optional[str] = None
    ) -> None:
        self.get_fuel(fuel_id, user_id)
        query = (
            self.client.table("fuel_logs")
            .update({"invoice_object_path": object_path})
            .eq("id", fuel_id)
        )
        if user_id is not None:
            query = query.eq("created_by", user_id)
        response = self._execute(query.select("id"))
        if not response.data:
            raise FleetManagementError(f"Fuel log {fuel_id} was not found or is not accessible")

    def list_fuel_logs(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        rows = self._related_list(
            "fuel_logs",
            "*,vehicle:vehicles(plate_number)",
            ("logged_on", "desc"),
            owner_id=user_id,
        )
        filtered = rows if user_id is None else self._filter_owned_rows(rows, user_id)
        trip_ids = list(dict.fromkeys(row.get("trip_id") for row in filtered))
        trips = self._select_by_values(
            "trips",
            "id,ism_no,origin,destination,route_number,route",
            "id",
            trip_ids,
            filters=[("created_by", user_id)] if user_id is not None else None,
        )
        trips_by_id = {trip["id"]: trip for trip in trips}
        for row in filtered:
            trip = trips_by_id.get(row.get("trip_id"))
            if trip:
                row["trip_ism_no"] = trip.get("ism_no")
                row["trip_origin"] = trip.get("origin")
                row["trip_destination"] = trip.get("destination")
                row["trip_route_number"] = trip.get("route_number")
                row["trip_route"] = trip.get("route")
        return filtered

    def add_trip(
        self,
        vehicle_id: int,
        driver_id: int,
        route: str,
        start_odometer: int,
        end_odometer: int,
        trip_date: Optional[str] = None,
        notes: Optional[str] = None,
        ism_no: Optional[str] = None,
        shipment_date: Optional[str] = None,
        time_in: Optional[str] = None,
        time_out: Optional[str] = None,
        origin: Optional[str] = None,
        destination: Optional[str] = None,
        load_details: Optional[str] = None,
        trip_fuel: Optional[str] = None,
        created_by: Optional[Any] = None,
        require_truck_rate: bool = False,
        trailer_id: Optional[int] = None,
        fuel_allocation: Optional[float] = None,
        actual_fuel_expense: Optional[float] = None,
        fuel_remarks: Optional[str] = None,
        fuel_invoice_object_path: Optional[str] = None,
        create_fuel_log: bool = False,
    ) -> Dict[str, Any]:
        if not self._exists("vehicles", vehicle_id):
            raise TripRateValidationError(f"Truck {vehicle_id} not found")
        truck = self.get_vehicle(vehicle_id)
        if truck.get("status") not in {"active", "available", "assigned"}:
            raise TripRateValidationError("This truck is inactive or under maintenance.")
        if not self._exists("drivers", driver_id):
            raise TripRateValidationError(f"Driver {driver_id} not found")
        if not route:
            raise FleetManagementError("route is required")
        if start_odometer < 0 or end_odometer < start_odometer:
            raise FleetManagementError("odometer readings must be non-negative and end cannot be lower than start")
        route_snapshot = (
            self._resolve_trip_route_rate(origin, destination, vehicle_id, trailer_id)
            if require_truck_rate
            else None
        )
        owner = self._normalize_owner(created_by)
        trip = self._insert(
            "trips",
            {
                "vehicle_id": vehicle_id,
                "truck_id": vehicle_id,
                "trailer_id": trailer_id,
                "driver_id": driver_id,
                "route": route.strip(),
                "start_odometer": int(start_odometer),
                "end_odometer": int(end_odometer),
                "trip_date": trip_date or datetime.now().date().isoformat(),
                "notes": notes,
                "ism_no": ism_no.strip() if ism_no else None,
                "shipment_date": shipment_date or trip_date or datetime.now().date().isoformat(),
                "time_in": time_in or None,
                "time_out": time_out or None,
                "origin": origin.strip() if origin else None,
                "destination": destination.strip() if destination else None,
                "load_details": load_details.strip() if load_details else None,
                "trip_fuel": trip_fuel.strip() if trip_fuel else None,
                "route_id": route_snapshot["route_id"] if route_snapshot else None,
                "route_number": route_snapshot["route_number"] if route_snapshot else None,
                "route_pair": route_snapshot["route_pair"] if route_snapshot else None,
                "pallet_capacity": route_snapshot["pallet_capacity"] if route_snapshot else None,
                "truck_route_rate_id": route_snapshot["rate_id"] if route_snapshot else None,
                "truck_route_rate": route_snapshot["rate"] if route_snapshot else None,
                "trip_rate_review_required": route_snapshot is None,
                "trailer_review_required": trailer_id is None,
                **({"created_by": owner} if owner is not None else {}),
            },
        )
        if end_odometer > 0:
            self._execute(
                self.client.table("vehicles")
                .update({"odometer": end_odometer})
                .eq("id", vehicle_id)
            )

        should_create_fuel = (
            create_fuel_log
            or fuel_allocation is not None
            or actual_fuel_expense is not None
            or fuel_remarks is not None
            or fuel_invoice_object_path is not None
        )
        if should_create_fuel:
            try:
                fuel_log = self.add_fuel(
                    vehicle_id=vehicle_id,
                    fuel_type="diesel",
                    quantity=None,
                    price_per_liter=None,
                    total_cost=actual_fuel_expense,
                    logged_on=shipment_date or trip_date or datetime.now().date().isoformat(),
                    created_by=owner,
                    trip_id=trip["id"],
                    fuel_allocation=fuel_allocation,
                    actual_expense=actual_fuel_expense,
                    remarks=fuel_remarks,
                    invoice_object_path=fuel_invoice_object_path,
                )
                trip["fuel_log"] = fuel_log
                trip["fuel_id"] = fuel_log.get("id")
                trip["fuel_allocation"] = fuel_log.get("fuel_allocation")
                trip["actual_fuel_expense"] = fuel_log.get("actual_expense")
                trip["actual_expense"] = fuel_log.get("actual_expense")
                trip["fuel_remarks"] = fuel_log.get("remarks")
                trip["fuel_invoice_object_path"] = fuel_log.get("invoice_object_path")
            except Exception as exc:
                try:
                    self._delete("trips", trip["id"])
                except Exception:
                    pass
                raise FleetManagementError(f"Failed to save fuel information with trip: {exc}") from exc

        return trip

    def get_trip(self, trip_id: int, user_id: Optional[str] = None) -> Dict[str, Any]:
        response = self._execute(
            self.client.table("trips")
            .select("*,driver:drivers(name),truck:vehicles!trips_truck_id_fkey(plate_number,make,model),trailer:trailers(plate_number,pallet_capacity,trailer_type,status)")
            .eq("id", trip_id)
            .limit(1)
        )
        if not response.data:
            raise FleetManagementError(f"Trip {trip_id} not found")
        row = dict(response.data[0])
        if user_id is not None and not self._matches_owner(row, user_id):
            raise FleetManagementError(f"You do not have access to trip {trip_id}")
        driver = row.pop("driver", None)
        vehicle = row.pop("truck", None)
        trailer = row.pop("trailer", None)
        if isinstance(driver, dict):
            row["driver_name"] = driver.get("name")
        if isinstance(vehicle, dict):
            row.update(
                {
                    key: vehicle.get(key)
                    for key in ("plate_number", "make", "model")
                }
            )
            row["truck_plate_number"] = vehicle.get("plate_number")
        if isinstance(trailer, dict):
            row["trailer_plate_number"] = trailer.get("plate_number")
            row["trailer_type"] = trailer.get("trailer_type")
            row["trailer_status"] = trailer.get("status")

        fuel_records = self._select_all("fuel_logs", "*", filters=[("trip_id", trip_id)])
        if fuel_records:
            fl = fuel_records[0]
            row["fuel_id"] = fl.get("id")
            row["fuel_allocation"] = fl.get("fuel_allocation")
            row["actual_fuel_expense"] = fl.get("actual_expense")
            row["actual_expense"] = fl.get("actual_expense")
            row["fuel_remarks"] = fl.get("remarks")
            row["fuel_invoice_object_path"] = fl.get("invoice_object_path")

        return row

    @staticmethod
    def _normalize_trip_time(value: Any, field_name: str) -> str:
        if value is None:
            raise FleetManagementError(f"{field_name} is required.")
        text = str(value).strip()
        if not text:
            raise FleetManagementError(f"{field_name} is required.")
        for pattern in ("%H:%M", "%H:%M:%S"):
            try:
                return datetime.strptime(text, pattern).strftime("%H:%M")
            except ValueError:
                pass
        try:
            iso_value = text[:-1] + "+00:00" if text.endswith("Z") else text
            parsed = datetime.fromisoformat(iso_value)
            return parsed.time().strftime("%H:%M")
        except ValueError as exc:
            raise FleetManagementError(f"{field_name} must be a valid time like 08:30.") from exc

    def record_trip_time_out(
        self,
        trip_id: int,
        time_value: Any,
        location: Optional[str],
        edited_by: str,
        editor_email: Optional[str],
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        current_trip = self.get_trip(trip_id, user_id)
        if current_trip.get("time_out") not in (None, ""):
            raise FleetManagementError("Time Out is already recorded for this trip. Use the correction workflow to change it.")
        if current_trip.get("time_in") not in (None, ""):
            raise FleetManagementError("This trip has already been completed and cannot be departed again.")
        departure_time = self._normalize_trip_time(time_value, "Time Out")
        departure_location = (location or current_trip.get("origin") or "").strip()
        if not departure_location:
            raise FleetManagementError("The departure location is required.")
        if current_trip.get("origin") and canonical_warehouse_code(current_trip.get("origin")) != canonical_warehouse_code(departure_location):
            raise FleetManagementError("The recorded departure location must match the trip origin.")
        update_values = {
            "shipment_date": current_trip.get("shipment_date") or current_trip.get("trip_date") or datetime.now().date().isoformat(),
            "origin": current_trip.get("origin") or departure_location,
            "destination": current_trip.get("destination"),
            "vehicle_id": current_trip.get("vehicle_id") or current_trip.get("truck_id"),
            "truck_id": current_trip.get("truck_id") or current_trip.get("vehicle_id"),
            "driver_id": current_trip.get("driver_id"),
            "route": current_trip.get("route") or f"{current_trip.get('origin') or departure_location} to {current_trip.get('destination') or ''}".strip(),
            "time_out": departure_time,
            "last_edited_by": edited_by,
            "last_edited_by_email": editor_email,
        }
        if not update_values["route"] or update_values["route"].endswith(" to "):
            update_values["route"] = current_trip.get("route") or "Recorded trip"
        return self.update_trip(trip_id, update_values, edited_by, editor_email, user_id=user_id)

    def record_trip_time_in(
        self,
        trip_id: int,
        time_value: Any,
        location: Optional[str],
        edited_by: str,
        editor_email: Optional[str],
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        current_trip = self.get_trip(trip_id, user_id)
        if current_trip.get("time_in") not in (None, ""):
            raise FleetManagementError("Time In is already recorded for this trip. Use the correction workflow to change it.")
        if current_trip.get("time_out") in (None, ""):
            raise FleetManagementError("This trip does not have a recorded Time Out. Record departure before arrival.")
        arrival_time = self._normalize_trip_time(time_value, "Time In")
        arrival_location = (location or current_trip.get("destination") or "").strip()
        if not arrival_location:
            raise FleetManagementError("The arrival location is required.")
        if current_trip.get("destination") and canonical_warehouse_code(current_trip.get("destination")) != canonical_warehouse_code(arrival_location):
            raise FleetManagementError("The recorded arrival location must match the trip destination.")
        update_values = {
            "shipment_date": current_trip.get("shipment_date") or current_trip.get("trip_date") or datetime.now().date().isoformat(),
            "origin": current_trip.get("origin"),
            "destination": current_trip.get("destination") or arrival_location,
            "vehicle_id": current_trip.get("vehicle_id") or current_trip.get("truck_id"),
            "truck_id": current_trip.get("truck_id") or current_trip.get("vehicle_id"),
            "driver_id": current_trip.get("driver_id"),
            "route": current_trip.get("route") or f"{current_trip.get('origin') or ''} to {current_trip.get('destination') or arrival_location}".strip(),
            "time_in": arrival_time,
            "last_edited_by": edited_by,
            "last_edited_by_email": editor_email,
        }
        if not update_values["route"] or update_values["route"].endswith(" to "):
            update_values["route"] = current_trip.get("route") or "Recorded trip"
        return self.update_trip(trip_id, update_values, edited_by, editor_email, user_id=user_id)

    def update_trip(
        self,
        trip_id: int,
        values: Dict[str, Any],
        edited_by: str,
        editor_email: Optional[str],
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        editable_fields = {
            "ism_no",
            "shipment_date",
            "time_in",
            "time_out",
            "origin",
            "destination",
            "vehicle_id",
            "driver_id",
            "load_details",
            "trip_fuel",
            "notes",
            "route",
            "truck_id",
            "trailer_id",
            "fuel_allocation",
            "actual_fuel_expense",
            "fuel_remarks",
        }
        required_fields = {
            "shipment_date",
            "origin",
            "destination",
            "vehicle_id",
            "driver_id",
            "route",
        }
        current_trip = self.get_trip(trip_id, user_id)
        normalized_values = dict(current_trip)
        normalized_values.update({k: v for k, v in values.items() if k in editable_fields})
        if "truck_id" in values and values.get("truck_id") is not None:
            normalized_values["truck_id"] = values["truck_id"]
        if "vehicle_id" in values and values.get("vehicle_id") is not None:
            normalized_values["vehicle_id"] = values["vehicle_id"]
        if "driver_id" in values and values.get("driver_id") is not None:
            normalized_values["driver_id"] = values["driver_id"]
        if "time_in" in values and values.get("time_in") is not None:
            normalized_values["time_in"] = values["time_in"]
        if "time_out" in values and values.get("time_out") is not None:
            normalized_values["time_out"] = values["time_out"]

        truck_id = normalized_values.get("truck_id") or normalized_values.get("vehicle_id")
        if truck_id is None:
            raise FleetManagementError("Trip update requires an assigned truck.")
        if not self._exists("vehicles", truck_id):
            raise FleetManagementError(f"Truck {truck_id} not found")
        previous_truck_id = current_trip.get("truck_id") or current_trip.get("vehicle_id")
        truck_changed = str(previous_truck_id or "") != str(truck_id or "")
        if truck_changed:
            truck = self.get_vehicle(truck_id)
            if truck.get("status") not in {"active", "available", "assigned"}:
                raise TripRateValidationError("This truck is inactive or under maintenance.")
        driver_id = normalized_values.get("driver_id")
        if driver_id is not None and not self._exists("drivers", driver_id):
            raise FleetManagementError(f"Driver {driver_id} not found")
        if not required_fields.issubset(normalized_values):
            raise FleetManagementError("The trip contains unsupported fields.")
        if set(values) - editable_fields:
            raise FleetManagementError("The trip contains unsupported fields.")

        fuel_values: Dict[str, Any] = {}
        if "fuel_allocation" in values:
            fuel_values["fuel_allocation"] = values["fuel_allocation"]
        if "actual_fuel_expense" in values:
            fuel_values["actual_expense"] = values["actual_fuel_expense"]
        if "fuel_remarks" in values:
            fuel_values["remarks"] = values["fuel_remarks"]

        route_origin = normalized_values.get("origin")
        route_destination = normalized_values.get("destination")
        rate_determining_fields_changed = (
            canonical_warehouse_code(current_trip.get("origin"))
            != canonical_warehouse_code(route_origin)
            or canonical_warehouse_code(current_trip.get("destination"))
            != canonical_warehouse_code(route_destination)
            or str(current_trip.get("trailer_id") or "")
            != str(normalized_values.get("trailer_id") or "")
        )
        update_values = {
            **{k: v for k, v in normalized_values.items() if k in editable_fields},
            "truck_id": truck_id,
            "vehicle_id": truck_id,
            "trip_date": normalized_values["shipment_date"],
            "last_edited_by": edited_by,
            "last_edited_by_email": editor_email,
        }
        if rate_determining_fields_changed:
            route_snapshot = self._resolve_trip_route_rate(
                route_origin,
                route_destination,
                truck_id,
                normalized_values.get("trailer_id"),
            )
            update_values.update(
                {
                    "route_id": route_snapshot["route_id"],
                    "route_number": route_snapshot["route_number"],
                    "route_pair": route_snapshot["route_pair"],
                    "pallet_capacity": route_snapshot["pallet_capacity"],
                    "truck_route_rate_id": route_snapshot["rate_id"],
                    "truck_route_rate": route_snapshot["rate"],
                    "trip_rate_review_required": False,
                    "trailer_review_required": False,
                }
            )
        query = (
            self.client.table("trips")
            .update(update_values)
            .eq("id", trip_id)
        )
        if user_id is not None:
            query = query.eq("created_by", user_id)
        response = self._execute(query.select("*"))
        if not response.data:
            raise FleetManagementError(f"Trip {trip_id} was not found or is not accessible")
        updated_trip = dict(response.data[0])

        if fuel_values:
            existing_fuel = self._select_all("fuel_logs", "*", filters=[("trip_id", trip_id)])
            if existing_fuel:
                self.update_fuel(
                    existing_fuel[0]["id"],
                    fuel_values,
                    edited_by=edited_by,
                    editor_email=editor_email,
                    user_id=user_id,
                )
            elif any(v is not None for v in fuel_values.values()):
                self.add_fuel(
                    vehicle_id=truck_id or current_trip.get("vehicle_id"),
                    fuel_type="diesel",
                    trip_id=trip_id,
                    fuel_allocation=fuel_values.get("fuel_allocation"),
                    actual_expense=fuel_values.get("actual_expense"),
                    remarks=fuel_values.get("remarks"),
                    created_by=user_id or current_trip.get("created_by"),
                )

        return updated_trip

    def list_trip_edit_history(
        self, trip_id: int, user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        self.get_trip(trip_id, user_id)
        response = self._execute(
            self.client.table("trip_edit_history")
            .select("id,trip_id,edited_by,edited_by_email,edited_at,old_values,new_values")
            .eq("trip_id", trip_id)
            .order("edited_at", desc=True)
        )
        return [dict(row) for row in (response.data or [])]

    def set_trip_manifest_path(
        self,
        trip_id: int,
        object_path: str,
        user_id: Optional[str] = None,
        edited_by: Optional[str] = None,
        editor_email: Optional[str] = None,
    ) -> None:
        self.get_trip(trip_id, user_id)
        update_values = {"manifest_object_path": object_path}
        if edited_by is not None:
            update_values["last_edited_by"] = edited_by
            update_values["last_edited_by_email"] = editor_email
        query = (
            self.client.table("trips")
            .update(update_values)
            .eq("id", trip_id)
        )
        if user_id is not None:
            query = query.eq("created_by", user_id)
        response = self._execute(query.select("id"))
        if not response.data:
            raise FleetManagementError(f"Trip {trip_id} was not found or is not accessible")

    def list_trips(
        self,
        user_id: Optional[str] = None,
        include_fuel: bool = True,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        date_filters: List[tuple[str, Any] | tuple[str, str, Any]] = []
        if start_date is not None:
            date_filters.append(("gte", "shipment_date", start_date))
        if end_date is not None:
            date_filters.append(("lte", "shipment_date", end_date))
        rows = self._related_list(
            "trips",
            "*,driver:drivers(name),truck:vehicles!trips_truck_id_fkey(plate_number,make,model),trailer:trailers(plate_number,pallet_capacity,trailer_type,status)",
            ("shipment_date", "desc"),
            owner_id=user_id,
            filters=date_filters,
        )
        filtered = rows if user_id is None else self._filter_owned_rows(rows, user_id)
        if include_fuel and filtered:
            fuel_logs = self._select_by_values(
                "fuel_logs",
                "id,trip_id,fuel_allocation,actual_expense,remarks,invoice_object_path",
                "trip_id",
                [row.get("id") for row in filtered],
                filters=[("created_by", user_id)] if user_id is not None else None,
            )
            fuel_by_trip = {
                fuel["trip_id"]: fuel
                for fuel in fuel_logs
                if fuel.get("trip_id") is not None
            }
            for row in filtered:
                fuel = fuel_by_trip.get(row.get("id"))
                if fuel:
                    row["fuel_id"] = fuel.get("id")
                    row["fuel_allocation"] = fuel.get("fuel_allocation")
                    row["actual_fuel_expense"] = fuel.get("actual_expense")
                    row["actual_expense"] = fuel.get("actual_expense")
                    row["fuel_remarks"] = fuel.get("remarks")
                    row["fuel_invoice_object_path"] = fuel.get("invoice_object_path")
        return filtered

    def payroll_report(self, start_date: str, end_date: str) -> Dict[str, Any]:
        from payroll import PayrollService

        return PayrollService(self).report(start_date, end_date)

    def revenue_dashboard(self, filters: Dict[str, Any]) -> Dict[str, Any]:
        response = self._execute(
            self.client.rpc("revenue_dashboard", filters)
        )
        data = response.data
        if isinstance(data, list):
            data = data[0] if data else None
        if not isinstance(data, dict):
            raise FleetManagementError("Supabase did not return a Revenue dashboard report")
        return dict(data)

    def set_trip_revenue_status(
        self,
        trip_id: int,
        status: str,
        reason: str,
        actor_id: str,
        actor_email: Optional[str],
    ) -> Dict[str, Any]:
        response = self._execute(
            self.client.rpc(
                "set_trip_revenue_status",
                {
                    "p_trip_id": trip_id,
                    "p_status": status,
                    "p_reason": reason,
                    "p_actor_id": actor_id,
                    "p_actor_email": actor_email,
                },
            )
        )
        data = response.data
        if isinstance(data, list):
            data = data[0] if data else None
        if not isinstance(data, dict):
            raise FleetManagementError("Supabase did not return the updated trip revenue status")
        return dict(data)

    def add_revenue_adjustment(
        self,
        trip_id: int,
        amount: Decimal,
        reason: str,
        actor_id: str,
        idempotency_key: str,
    ) -> Dict[str, Any]:
        response = self._execute(
            self.client.rpc(
                "add_revenue_adjustment",
                {
                    "p_trip_id": trip_id,
                    "p_amount": format(amount, ".2f"),
                    "p_reason": reason,
                    "p_actor_id": actor_id,
                    "p_idempotency_key": idempotency_key,
                },
            )
        )
        data = response.data
        if isinstance(data, list):
            data = data[0] if data else None
        if not isinstance(data, dict):
            raise FleetManagementError("Supabase did not return the revenue adjustment")
        return dict(data)

    def review_payroll(
        self, start_date: str, end_date: str, actor_id: str
    ) -> Dict[str, Any]:
        from payroll import PayrollService

        return PayrollService(self).review(start_date, end_date, actor_id)

    def add_cash_advance(
        self,
        start_date: str,
        end_date: str,
        driver_id: int,
        advance_date: str,
        amount: Any,
        remarks: Optional[str],
        reference: Optional[str],
        actor_id: str,
    ) -> Dict[str, Any]:
        from payroll import PayrollService

        return PayrollService(self).add_cash_advance(
            start_date, end_date, driver_id, advance_date, amount, remarks,
            reference, actor_id,
        )

    def add_overdraft(
        self,
        driver_id: int,
        transaction_type: str,
        amount: Any,
        effective_date: str,
        remarks: Optional[str],
        actor_id: str,
    ) -> Dict[str, Any]:
        from payroll import PayrollService

        return PayrollService(self).add_overdraft(
            driver_id, transaction_type, amount, effective_date, remarks, actor_id
        )

    def finalize_payroll(
        self,
        start_date: str,
        end_date: str,
        settle_overdraft: bool,
        actor_id: str,
    ) -> Dict[str, Any]:
        from payroll import PayrollService

        return PayrollService(self).finalize(
            start_date, end_date, settle_overdraft, actor_id
        )

    def list_truck_route_rates(self) -> List[Dict[str, Any]]:
        return self._list("truck_route_rates", order=("origin_code", "asc"))

    def list_truck_routes(self) -> List[Dict[str, Any]]:
        return self._list("truck_routes", order=("route_number", "asc"))

    def list_trailers(self) -> List[Dict[str, Any]]:
        return self._list("trailers", order=("plate_number", "asc"))

    def get_trailer(self, trailer_id: int) -> Dict[str, Any]:
        return self._get("trailers", trailer_id)

    def delete_trailer(self, trailer_id: int) -> None:
        self.get_trailer(trailer_id)
        assigned = self._select_all("trips", "id", filters=[("trailer_id", trailer_id)])
        if assigned:
            raise FleetManagementError(
                "This trailer is present in trip history. Mark it inactive instead of deleting it."
            )
        self._delete("trailers", trailer_id)

    def _resolve_trip_route_rate(
        self,
        origin: Optional[str],
        destination: Optional[str],
        truck_id: Optional[int],
        trailer_id: Optional[int],
    ) -> Dict[str, Any]:
        origin_code = canonical_warehouse_code(origin)
        destination_code = canonical_warehouse_code(destination)
        if not origin_code or not destination_code:
            raise TripRateValidationError("Select a valid configured origin and destination.")
        if origin_code == destination_code:
            raise TripRateValidationError("Origin and destination must be different locations.")
        route = next(
            (
                row for row in self.list_truck_routes()
                if row.get("active") is not False
                and row.get("origin_code") == origin_code
                and row.get("destination_code") == destination_code
            ),
            None,
        )
        if route is None:
            raise TripRateValidationError(
                f"No configured route exists from {origin_code} to {destination_code}."
            )
        if truck_id is None:
            raise TripRateValidationError("Select an active truck.")
        if not self._exists("vehicles", truck_id):
            raise TripRateValidationError("Select an existing truck.")
        if trailer_id is None or not self._exists("trailers", trailer_id):
            raise TripRateValidationError("Select an existing active trailer.")
        try:
            trailer = self.get_trailer(trailer_id)
            if trailer.get("status") != "active":
                raise TripRateValidationError("This trailer is inactive or under maintenance.")
            capacity = int(trailer.get("pallet_capacity"))
        except (TypeError, ValueError) as exc:
            raise TripRateValidationError(
                "This trailer has no valid pallet capacity."
            ) from exc
        if capacity <= 0:
            raise TripRateValidationError("This trailer has no valid pallet capacity.")
        rate_row = next(
            (
                row for row in self.list_truck_route_rates()
                if row.get("active") is not False
                and row.get("origin_code") == origin_code
                and row.get("destination_code") == destination_code
                and int(row.get("pallet_capacity") or 0) == capacity
            ),
            None,
        )
        if rate_row is None or rate_row.get("hauling_rate") is None:
            raise TripRateValidationError(
                f"Rate not configured for {origin_code} to {destination_code} "
                f"at {capacity} pallets. The trip cannot be saved."
            )
        try:
            rate = Decimal(str(rate_row["hauling_rate"])).quantize(Decimal("0.01"))
        except (InvalidOperation, KeyError) as exc:
            raise TripRateValidationError("The configured truck route rate is invalid.") from exc
        return {
            "route_id": route["id"],
            "route_number": route["route_number"],
            "route_pair": route["route_pair"],
            "pallet_capacity": capacity,
            "trailer_id": trailer_id,
            "rate_id": rate_row["id"],
            "rate": format(rate, ".2f"),
        }

    def resolve_truck_route_rate(
        self,
        origin: Optional[str],
        destination: Optional[str],
        pallet_capacity: Any,
    ) -> Optional[Decimal]:
        origin_code = canonical_warehouse_code(origin)
        destination_code = canonical_warehouse_code(destination)
        if not origin_code or not destination_code:
            return None
        try:
            capacity = int(pallet_capacity)
        except (TypeError, ValueError):
            return None
        for row in self.list_truck_route_rates():
            if row.get("active") is False:
                continue
            if (
                row.get("origin_code") == origin_code
                and row.get("destination_code") == destination_code
                and int(row.get("pallet_capacity") or 0) == capacity
            ):
                value = row.get("hauling_rate")
                if value is None:
                    return None
                try:
                    return Decimal(str(value))
                except InvalidOperation:
                    return None
        return None

    def resolve_route_fuel_allocation(
        self, origin: Optional[str], destination: Optional[str]
    ) -> Optional[Decimal]:
        origin_code = canonical_warehouse_code(origin)
        destination_code = canonical_warehouse_code(destination)
        if not origin_code or not destination_code or origin_code == destination_code:
            return None
        route = next(
            (
                row for row in self.list_truck_routes()
                if row.get("active") is not False
                and row.get("origin_code") == origin_code
                and row.get("destination_code") == destination_code
            ),
            None,
        )
        if route is None:
            return None
        raw_allocation = route.get("fuel_allocation")
        if raw_allocation is None or raw_allocation == "":
            return None
        try:
            return Decimal(str(raw_allocation)).quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError, ValueError):
            return None

    def delete_trip(self, trip_id: int, user_id: Optional[str] = None) -> None:
        if user_id is not None:
            row = self.get_trip(trip_id)
            if not self._matches_owner(row, user_id):
                raise FleetManagementError(f"You do not have access to trip {trip_id}")
        try:
            self._delete("trips", trip_id)
        except FleetManagementError as exc:
            if "dispatch_movements_canonical_trip_id_fkey" in str(exc).lower():
                raise FleetManagementError(
                    "This trip is linked to a completed dispatch movement and "
                    "cannot be deleted. The movement history must be preserved."
                ) from exc
            raise

    def delete_maintenance(self, maintenance_id: int, user_id: Optional[str] = None) -> None:
        if user_id is not None:
            row = self.get_maintenance(maintenance_id)
            if not self._matches_owner(row, user_id):
                raise FleetManagementError(f"You do not have access to maintenance record {maintenance_id}")
        self._delete("maintenance", maintenance_id)

    def delete_fuel_log(self, fuel_id: int, user_id: Optional[str] = None) -> None:
        if user_id is not None:
            row = self.get_fuel(fuel_id)
            if not self._matches_owner(row, user_id):
                raise FleetManagementError(f"You do not have access to fuel log {fuel_id}")
        self._delete("fuel_logs", fuel_id)

    def dashboard(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        vehicles = self._list("vehicles", select="status")
        drivers = self._list("drivers", select="status")
        fuel_logs = self._filter_owned_rows(self._list("fuel_logs", select="total_cost"), user_id)
        maintenance = self._filter_owned_rows(self._list("maintenance", select="cost"), user_id)
        trips = self._filter_owned_rows(self._list("trips", select="id"), user_id)
        return {
            "total_vehicles": len(vehicles),
            "active_drivers": sum(driver["status"] == "active" for driver in drivers),
            "assigned_vehicles": sum(vehicle["status"] == "assigned" for vehicle in vehicles),
            "total_fuel_spend": sum(float(item["total_cost"]) for item in fuel_logs),
            "total_maintenance": sum(float(item["cost"]) for item in maintenance),
            "recent_trips": len(trips),
        }

    def export_report(self, output_path: str) -> Dict[str, Any]:
        from excel_report import build_excel_report

        data = {
            "vehicles": self.list_vehicles(),
            "trailers": self.list_trailers(),
            "drivers": self.list_drivers(),
            "assignments": self.list_assignments(),
            "trips": self.list_trips(),
            "maintenance": self.list_maintenance(),
            "fuel_logs": self.list_fuel_logs(),
            "dashboard": self.dashboard(),
        }
        with open(output_path, "wb") as handle:
            handle.write(build_excel_report(data).getvalue())
        return {
            "output_path": output_path,
            "records_written": sum(
                len(value) for value in data.values() if isinstance(value, list)
            ),
        }


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Good Luck Forwarding Systems Inc. Fleet Management System"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_vehicle = subparsers.add_parser("add-vehicle", help="Add a new vehicle")
    add_vehicle.add_argument("--plate-number", required=True)
    add_vehicle.add_argument("--make", required=True)
    add_vehicle.add_argument("--model", required=True)
    add_vehicle.add_argument("--year", type=int, required=True)
    add_vehicle.add_argument("--color")
    add_vehicle.add_argument("--status", default="available")
    add_vehicle.add_argument("--odometer", type=int, default=0)
    add_vehicle.add_argument("--registration-expiry")
    add_vehicle.add_argument("--insurance-expiry")

    add_driver = subparsers.add_parser("add-driver", help="Add a new driver")
    add_driver.add_argument("--name", required=True)
    add_driver.add_argument("--license-number", required=True)
    add_driver.add_argument("--phone")
    add_driver.add_argument("--email")
    add_driver.add_argument("--status", default="active")

    assignment = subparsers.add_parser("assign-vehicle", help="Assign a vehicle to a driver")
    assignment.add_argument("--driver-id", type=int, required=True)
    assignment.add_argument("--vehicle-id", type=int, required=True)
    assignment.add_argument("--assigned-date")
    assignment.add_argument("--notes")

    maintenance = subparsers.add_parser("add-maintenance", help="Record maintenance")
    maintenance.add_argument("--vehicle-id", type=int, required=True)
    maintenance.add_argument("--service-type", required=True)
    maintenance.add_argument("--description")
    maintenance.add_argument("--cost", type=float, default=0.0)
    maintenance.add_argument("--performed-on")

    fuel = subparsers.add_parser("add-fuel", help="Record fuel purchase")
    fuel.add_argument("--vehicle-id", type=int, required=True)
    fuel.add_argument("--fuel-type", required=True)
    fuel.add_argument("--quantity", type=float, required=True)
    fuel.add_argument("--price-per-liter", type=float, required=True)
    fuel.add_argument("--total-cost", type=float)
    fuel.add_argument("--logged-on")

    trip = subparsers.add_parser("add-trip", help="Record a trip")
    trip.add_argument("--vehicle-id", type=int, required=True)
    trip.add_argument("--driver-id", type=int, required=True)
    trip.add_argument("--route", required=True)
    trip.add_argument("--start-odometer", type=int, required=True)
    trip.add_argument("--end-odometer", type=int, required=True)
    trip.add_argument("--trip-date")
    trip.add_argument("--notes")

    subparsers.add_parser("list-vehicles", help="List all vehicles")
    subparsers.add_parser("list-drivers", help="List all drivers")
    subparsers.add_parser("list-assignments", help="List vehicle assignments")
    subparsers.add_parser("list-trips", help="List recorded trips")
    subparsers.add_parser("dashboard", help="Display fleet summary")

    export = subparsers.add_parser("export-report", help="Export fleet data to formatted Excel")
    export.add_argument("--output", default="fleet_system_report.xlsx")
    return parser


def main() -> None:
    parser = _build_cli()
    args = parser.parse_args()
    try:
        manager = FleetManager()
        if args.command == "add-vehicle":
            result = manager.add_vehicle(
                args.plate_number, args.make, args.model, args.year, args.color,
                args.status, args.odometer, args.registration_expiry, args.insurance_expiry,
            )
        elif args.command == "add-driver":
            result = manager.add_driver(
                args.name, args.license_number, args.phone, args.email, args.status
            )
        elif args.command == "assign-vehicle":
            result = manager.assign_vehicle(
                args.driver_id, args.vehicle_id, args.assigned_date, args.notes
            )
        elif args.command == "add-maintenance":
            result = manager.add_maintenance(
                args.vehicle_id, args.service_type, args.description, args.cost, args.performed_on
            )
        elif args.command == "add-fuel":
            result = manager.add_fuel(
                args.vehicle_id, args.fuel_type, args.quantity,
                args.price_per_liter, args.total_cost, args.logged_on,
            )
        elif args.command == "add-trip":
            result = manager.add_trip(
                args.vehicle_id, args.driver_id, args.route, args.start_odometer,
                args.end_odometer, args.trip_date, args.notes,
            )
        elif args.command == "list-vehicles":
            result = manager.list_vehicles()
        elif args.command == "list-drivers":
            result = manager.list_drivers()
        elif args.command == "list-assignments":
            result = manager.list_assignments()
        elif args.command == "list-trips":
            result = manager.list_trips()
        elif args.command == "dashboard":
            result = manager.dashboard()
        elif args.command == "export-report":
            result = manager.export_report(args.output)
        else:
            parser.error(f"Unsupported command: {args.command}")
            return
        _print_json(result)
    except FleetManagementError as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
