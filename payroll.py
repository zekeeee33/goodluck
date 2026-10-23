from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from fleet_management import FleetManagementError

SHORT_ROUTES = {
    frozenset(("DAV2", "PLAS")),
    frozenset(("DAV1", "DAV2")),
    frozenset(("DAV1", "PLAS")),
}
LONG_ROUTES = {
    frozenset(("GENSAN", "DAV2")),
    frozenset(("GENSAN", "PLAS")),
    frozenset(("GENSAN", "DAV1")),
}


def _normalized_driver_name(value: Any) -> str:
    return " ".join(str(value or "").split()).casefold()


def trip_rate(origin: str | None, destination: str | None) -> Decimal | None:
    if not origin or not destination:
        return None
    route = frozenset((origin.strip().upper(), destination.strip().upper()))
    if route in SHORT_ROUTES:
        return Decimal("200.00")
    if route in LONG_ROUTES:
        return Decimal("900.00")
    return None


def period_date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a valid date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid date") from exc


def calculate_driver_payroll(
    trips: list[dict[str, Any]],
    advances: list[dict[str, Any]],
    overdraft_balance: Any,
    settle_overdraft: bool = False,
) -> dict[str, Decimal]:
    gross = sum(
        (Decimal(str(trip["rate"])) for trip in trips), Decimal("0.00")
    )
    cash_advances = sum(
        (Decimal(str(advance["amount"])) for advance in advances), Decimal("0.00")
    )
    before_overdraft = gross - cash_advances
    balance = Decimal(str(overdraft_balance or "0"))
    overdraft_deduction = (
        min(max(before_overdraft, Decimal("0")), balance)
        if settle_overdraft else Decimal("0.00")
    )
    return {
        "gross_pay": gross,
        "cash_advances": cash_advances,
        "net_before_overdraft": before_overdraft,
        "overdraft_balance": balance,
        "overdraft_deduction": overdraft_deduction,
        "final_net_pay": max(before_overdraft - overdraft_deduction, Decimal("0")),
        "remaining_amount_due": max(-before_overdraft, Decimal("0")),
        "remaining_overdraft": balance - overdraft_deduction,
    }


class PayrollService:
    def __init__(self, manager: Any):
        self.manager = manager
        self.client = manager.client
        self.execute = manager._execute

    def _rows(self, table: str, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        page_size = 1000
        offset = 0
        result: list[dict[str, Any]] = []
        while True:
            query = self.client.table(table).select("*")
            for field, value in (filters or {}).items():
                query = query.eq(field, value)
            response = self.execute(
                query.order("id").range(offset, offset + page_size - 1)
            )
            page = response.data or []
            result.extend(dict(row) for row in page)
            if len(page) < page_size:
                return result
            offset += page_size

    def _get_period(self, start_date: str, end_date: str) -> dict[str, Any] | None:
        query = (
            self.client.table("payroll_periods")
            .select("*")
            .eq("start_date", start_date)
            .eq("end_date", end_date)
            .limit(1)
        )
        rows = self.execute(query).data or []
        return dict(rows[0]) if rows else None

    def _create_period(self, start_date: str, end_date: str, actor_id: str) -> dict[str, Any]:
        period = self._get_period(start_date, end_date)
        if period:
            return period
        response = self.execute(
            self.client.table("payroll_periods").insert(
                {"start_date": start_date, "end_date": end_date, "created_by": actor_id}
            ).select("*")
        )
        rows = response.data or []
        if not rows:
            raise FleetManagementError("Payroll period was not returned by the database")
        return dict(rows[0])

    @staticmethod
    def _trip_date(trip: dict[str, Any]) -> str | None:
        return trip.get("shipment_date") or trip.get("trip_date") or trip.get("record_date")

    def report(self, start_date: str, end_date: str) -> dict[str, Any]:
        start = period_date(start_date, "Start date")
        end = period_date(end_date, "End date")
        if start > end:
            raise ValueError("Start date must be on or before end date")

        period = self._get_period(start_date, end_date)
        drivers = self.manager.list_drivers()
        if period and period.get("status") in {"reviewed", "finalized"}:
            saved_items = self._rows("payroll_items", {"payroll_period_id": period["id"]})
            trips = saved_items
        else:
            trip_rows = self.manager.list_trips(
                include_fuel=False,
                start_date=start_date,
                end_date=end_date,
            )
            trips = []
            for trip in trip_rows:
                trip_date = self._trip_date(trip)
                if not trip_date or not start_date <= str(trip_date) <= end_date:
                    continue
                trip = {**trip, "payroll_date": trip_date}
                trips.append(trip)

        advances = (
            self._rows("cash_advances", {"payroll_period_id": period["id"]})
            if period else []
        )
        audit_history = (
            self._rows("payroll_audit", {"payroll_period_id": period["id"]})
            if period else []
        )
        overdraft_rows = self._rows("overdraft_transactions")
        drivers_by_id = {str(driver["id"]): driver for driver in drivers}
        drivers_by_name: dict[str, list[dict[str, Any]]] = {}
        drivers_by_last_name: dict[str, list[dict[str, Any]]] = {}
        for driver in drivers:
            name_key = _normalized_driver_name(driver.get("name"))
            if name_key:
                drivers_by_name.setdefault(name_key, []).append(driver)
                last_name_key = name_key.split()[-1].strip(".,")
                if last_name_key:
                    drivers_by_last_name.setdefault(last_name_key, []).append(driver)
        period_status_by_id = {
            str(item["id"]): item.get("status")
            for item in self._rows("payroll_periods")
        }
        finalized_trip_ids = {
            str(item["trip_id"])
            for item in self._rows("payroll_items")
            if period_status_by_id.get(str(item.get("payroll_period_id"))) == "finalized"
            and (not period or str(item.get("payroll_period_id")) != str(period.get("id")))
        }
        rows: list[dict[str, Any]] = []
        issues: list[dict[str, Any]] = []
        for trip in trips:
            trip_id = str(trip.get("trip_id", trip.get("id", "")))
            if period and period.get("status") in {"reviewed", "finalized"}:
                row = dict(trip)
                row["payroll_item_id"] = trip.get("id")
                row["id"] = trip.get("trip_id")
                row.setdefault("driver_id", trip.get("driver_id"))
                row.setdefault("driver_name", trip.get("driver_name"))
                row.setdefault("payroll_date", trip.get("trip_date"))
                row["rate"] = trip.get("rate")
                row["driver_key"] = (
                    f"id:{row['driver_id']}" if row.get("driver_id")
                    else f"name:{' '.join(str(row.get('driver_name') or 'Unassigned driver').split()).casefold()}"
                )
                row["eligible"] = True
                row["issue"] = None
                rows.append(row)
                continue
            driver = drivers_by_id.get(str(trip.get("driver_id")))
            if driver is None:
                name_key = _normalized_driver_name(trip.get("driver_name"))
                matches = drivers_by_name.get(name_key, [])
                if not matches and len(name_key.split()) == 1:
                    last_name_key = name_key.strip(".,")
                    matches = drivers_by_last_name.get(last_name_key, [])
                if len(matches) == 1:
                    driver = matches[0]
            driver_id = driver["id"] if driver else trip.get("driver_id")
            driver_name = (driver or {}).get("name") or trip.get("driver_name")
            driver_key = (
                f"id:{driver_id}" if driver_id
                else f"name:{' '.join(str(driver_name or 'Unassigned driver').split()).casefold()}"
            )
            rate = trip_rate(trip.get("origin"), trip.get("destination"))
            issue = None
            if not trip.get("origin") or not trip.get("destination"):
                issue = "Missing origin or destination"
            elif rate is None:
                issue = "Unconfigured Route"
            elif trip_id in finalized_trip_ids:
                issue = "Already included in a finalized payroll"
            row = {
                **trip,
                "id": trip.get("id"),
                "driver_id": driver_id,
                "driver_key": driver_key,
                "payroll_date": trip.get("payroll_date"),
                "driver_name": driver_name or "Unassigned driver",
                "rate": str(rate) if rate is not None else None,
                "eligible": issue is None,
                "issue": issue,
            }
            if issue:
                issues.append(row)
            rows.append(row)

        by_driver: dict[str, dict[str, Any]] = {}
        for driver in drivers:
            driver_id = str(driver["id"])
            driver_key = f"id:{driver_id}"
            by_driver[driver_key] = {
                "driver_id": driver["id"],
                "driver_key": driver_key,
                "driver_name": driver["name"],
                "trips": [],
                "cash_advances": [],
                "opening_overdraft": Decimal("0.00"),
                "new_overdraft": Decimal("0.00"),
                "overdraft_deductions": Decimal("0.00"),
                "overdraft_transactions": [],
            }
        for row in rows:
            driver_key = row["driver_key"]
            driver = by_driver.get(driver_key)
            if driver is None:
                driver = {
                    "driver_id": None,
                    "driver_key": driver_key,
                    "driver_name": row["driver_name"],
                    "trips": [],
                    "cash_advances": [],
                    "opening_overdraft": Decimal("0.00"),
                    "new_overdraft": Decimal("0.00"),
                    "overdraft_deductions": Decimal("0.00"),
                    "overdraft_transactions": [],
                }
                by_driver[driver_key] = driver
            driver["trips"].append(row)
        for advance in advances:
            driver = by_driver.get(str(advance.get("driver_id")))
            if driver:
                driver["cash_advances"].append(advance)
        for transaction in overdraft_rows:
            driver = by_driver.get(str(transaction.get("driver_id")))
            if not driver or str(transaction.get("effective_date", "")) > end_date:
                continue
            driver["overdraft_transactions"].append(transaction)
            kind = transaction.get("transaction_type")
            amount = Decimal(str(transaction.get("amount", 0)))
            if kind == "opening":
                driver["opening_overdraft"] += amount
            elif kind == "new":
                driver["new_overdraft"] += amount
            elif kind == "deduction":
                driver["overdraft_deductions"] += amount

        summaries = []
        for driver in by_driver.values():
            valid_trips = [trip for trip in driver["trips"] if trip.get("eligible")]
            balance = max(
                driver["opening_overdraft"] + driver["new_overdraft"]
                - driver["overdraft_deductions"], Decimal("0.00")
            )
            totals = calculate_driver_payroll(
                valid_trips, driver["cash_advances"], balance
            )
            summaries.append(
                {
                    "driver_id": driver["driver_id"],
                    "driver_key": driver["driver_key"],
                    "driver_name": driver["driver_name"],
                    "total_trips": len(valid_trips),
                    "opening_overdraft": str(driver["opening_overdraft"]),
                    "new_overdraft": str(driver["new_overdraft"]),
                    "overdraft_transactions": driver["overdraft_transactions"],
                    **{key: str(value) for key, value in totals.items()},
                }
            )

        if period and period.get("status") == "finalized":
            summary_rows = self._rows(
                "payroll_summaries", {"payroll_period_id": period["id"]}
            )
            if summary_rows:
                summaries = [
                    {
                        **{
                            key: str(value) if isinstance(value, Decimal) else value
                            for key, value in row.items()
                        },
                        "overdraft_balance": row.get("remaining_overdraft", "0"),
                        "overdraft_transactions": by_driver.get(
                            str(row["driver_id"]), {}
                        ).get("overdraft_transactions", []),
                    }
                    for row in summary_rows
                ]
        return {
            "period": period,
            "drivers": summaries,
            "trips": rows,
            "issues": issues,
            "cash_advances": advances,
            "audit_history": sorted(
                audit_history,
                key=lambda entry: str(entry.get("created_at", "")),
                reverse=True,
            ),
            "status": period.get("status", "draft") if period else "draft",
        }

    def review(self, start_date: str, end_date: str, actor_id: str) -> dict[str, Any]:
        current = self.report(start_date, end_date)
        if current["status"] == "finalized":
            raise ValueError("Finalized payroll cannot be reviewed or edited")
        if current["issues"]:
            raise ValueError("Resolve all flagged trips before reviewing this payroll")
        if any(
            trip.get("eligible") and (not trip.get("driver_id") or not trip.get("ism_no"))
            for trip in current["trips"]
        ):
            raise ValueError(
                "Assign each payroll trip to a registered driver and provide its "
                "ISM number before reviewing this payroll"
            )
        period = self._create_period(start_date, end_date, actor_id)
        if period.get("status") != "draft":
            raise ValueError("Only a draft payroll can be reviewed")
        items = [
            {
                "payroll_period_id": period["id"],
                "trip_id": trip["id"],
                "driver_id": trip["driver_id"],
                "driver_name": trip["driver_name"],
                "trip_date": trip["payroll_date"],
                "ism_no": trip["ism_no"],
                "origin": trip["origin"],
                "destination": trip["destination"],
                "rate": trip["rate"],
                "truck_route_rate": trip.get("truck_route_rate"),
            }
            for trip in current["trips"]
            if trip.get("eligible")
        ]
        if items:
            response = self.execute(
                self.client.table("payroll_items").insert(items).select("*")
            )
            if getattr(response, "data", None) is None:
                raise FleetManagementError("Payroll trip details could not be saved")
        self.execute(
            self.client.table("payroll_periods")
            .update({
                "status": "reviewed",
                "reviewed_by": actor_id,
                "reviewed_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("id", period["id"])
        )
        self.execute(
            self.client.table("payroll_audit").insert(
                {
                    "payroll_period_id": period["id"],
                    "actor_id": actor_id,
                    "action": "reviewed",
                    "details": {"trip_count": len(items)},
                }
            )
        )
        return self.report(start_date, end_date)

    def add_cash_advance(
        self,
        start_date: str,
        end_date: str,
        driver_id: int,
        advance_date: str,
        amount: Any,
        remarks: str | None,
        reference: str | None,
        actor_id: str,
    ) -> dict[str, Any]:
        start = period_date(start_date, "Start date")
        end = period_date(end_date, "End date")
        day = period_date(advance_date, "Advance date")
        if start > end or day < start or day > end:
            raise ValueError("Cash advance date must be within the payroll period")
        try:
            value = Decimal(str(amount))
        except (InvalidOperation, TypeError) as exc:
            raise ValueError("Cash advance amount must be a positive number") from exc
        if not value.is_finite() or value <= 0 or value > Decimal("9999999999.99"):
            raise ValueError("Cash advance amount must be a positive number within the supported limit")
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("Cash advance amount cannot have more than two decimal places")
        if not self.manager._exists("drivers", driver_id):
            raise ValueError("Driver does not exist")
        period = self._create_period(start_date, end_date, actor_id)
        if period.get("status") != "draft":
            raise ValueError("Cash advances cannot be changed after payroll review")
        if reference:
            existing = self._rows("cash_advances", {"reference": reference})
            if existing:
                raise ValueError("A cash advance with this reference already exists")
        response = self.execute(
            self.client.table("cash_advances").insert(
                {
                    "payroll_period_id": period["id"],
                    "driver_id": driver_id,
                    "advance_date": advance_date,
                    "amount": str(value.quantize(Decimal("0.01"))),
                    "remarks": remarks,
                    "reference": reference,
                    "created_by": actor_id,
                }
            ).select("*")
        )
        rows = response.data or []
        if not rows:
            raise FleetManagementError("Cash advance was not returned by the database")
        advance = dict(rows[0])
        self.execute(
            self.client.table("payroll_audit").insert(
                {
                    "payroll_period_id": period["id"],
                    "actor_id": actor_id,
                    "action": "cash_advance_added",
                    "details": {"cash_advance_id": advance["id"], "amount": str(value)},
                }
            )
        )
        return advance

    def add_overdraft(
        self,
        driver_id: int,
        transaction_type: str,
        amount: Any,
        effective_date: str,
        remarks: str | None,
        actor_id: str,
    ) -> dict[str, Any]:
        if transaction_type not in {"opening", "new"}:
            raise ValueError("Overdraft transaction must be opening or new")
        period_date(effective_date, "Effective date")
        try:
            value = Decimal(str(amount))
        except (InvalidOperation, TypeError) as exc:
            raise ValueError("Overdraft amount must be a positive number") from exc
        if not value.is_finite() or value <= 0 or value > Decimal("9999999999.99"):
            raise ValueError("Overdraft amount must be a positive number within the supported limit")
        if value != value.quantize(Decimal("0.01")):
            raise ValueError("Overdraft amount cannot have more than two decimal places")
        if not self.manager._exists("drivers", driver_id):
            raise ValueError("Driver does not exist")
        response = self.execute(
            self.client.table("overdraft_transactions").insert(
                {
                    "driver_id": driver_id,
                    "transaction_type": transaction_type,
                    "amount": str(value.quantize(Decimal("0.01"))),
                    "effective_date": effective_date,
                    "remarks": remarks,
                    "created_by": actor_id,
                }
            ).select("*")
        )
        rows = response.data or []
        if not rows:
            raise FleetManagementError("Overdraft transaction was not returned by the database")
        transaction = dict(rows[0])
        self.execute(
            self.client.table("payroll_audit").insert(
                {
                    "actor_id": actor_id,
                    "action": "overdraft_transaction_added",
                    "details": {
                        "overdraft_transaction_id": transaction["id"],
                        "driver_id": driver_id,
                        "transaction_type": transaction_type,
                        "amount": str(value),
                    },
                }
            )
        )
        return transaction

    def finalize(self, start_date: str, end_date: str, settle_overdraft: bool, actor_id: str) -> dict[str, Any]:
        report = self.report(start_date, end_date)
        if not report["period"] or report["status"] != "reviewed":
            raise ValueError("Review the payroll before finalizing it")
        if report["issues"]:
            raise ValueError("Payroll contains trips requiring review")
        response = self.execute(
            self.client.rpc(
                "finalize_payroll_period",
                {
                    "p_period_id": report["period"]["id"],
                    "p_actor_id": actor_id,
                    "p_settle_overdraft": settle_overdraft,
                },
            )
        )
        if not response.data:
            raise FleetManagementError("Payroll finalization returned no result")
        return self.report(start_date, end_date)
