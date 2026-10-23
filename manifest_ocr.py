from __future__ import annotations

import os
import re
from datetime import datetime
from decimal import Decimal
from io import BytesIO
from typing import Any

from PIL import Image

WAREHOUSE_ALIASES = {
    "GENSAN DISTRIBUTION CENTER": "GENSAN",
    "GENSAN": "GENSAN",
    "Davao Bottling Plant 2": "DAV2",
    "DAV2": "DAV2",
    "Davao Bottling Plant 1": "DAV1",
    "DAV1": "DAV1",
    "PLAS Astorga": "PLAS",
    "PLAS": "PLAS",
}

TRUCK_ROUTE_RATE_CONFIG = [
    {"origin": "DAV1", "destination": "GENSAN", "pallet_capacity": 36, "rate": Decimal("12284.85")},
    {"origin": "DAV1", "destination": "GENSAN", "pallet_capacity": 46, "rate": Decimal("15500.00")},
    {"origin": "DAV1", "destination": "PLAS", "pallet_capacity": 36, "rate": Decimal("1847.00")},
    {"origin": "DAV1", "destination": "PLAS", "pallet_capacity": 46, "rate": Decimal("2300.00")},
    {"origin": "DAV2", "destination": "GENSAN", "pallet_capacity": 36, "rate": Decimal("11000.00")},
    {"origin": "DAV2", "destination": "GENSAN", "pallet_capacity": 46, "rate": Decimal("14000.00")},
    {"origin": "DAV2", "destination": "DAV1", "pallet_capacity": 46, "rate": Decimal("2300.00")},
    {"origin": "DAV2", "destination": "PLAS", "pallet_capacity": 36, "rate": Decimal("1847.00")},
    {"origin": "DAV2", "destination": "PLAS", "pallet_capacity": 46, "rate": Decimal("2200.00")},
    {"origin": "GENSAN", "destination": "DAV2", "pallet_capacity": 36, "rate": Decimal("11000.00")},
    {"origin": "GENSAN", "destination": "DAV2", "pallet_capacity": 46, "rate": Decimal("14000.00")},
    {"origin": "GENSAN", "destination": "DAV1", "pallet_capacity": 36, "rate": Decimal("12284.85")},
    {"origin": "GENSAN", "destination": "DAV1", "pallet_capacity": 46, "rate": Decimal("15500.00")},
    {"origin": "GENSAN", "destination": "PLAS", "pallet_capacity": 36, "rate": Decimal("11000.00")},
    {"origin": "GENSAN", "destination": "PLAS", "pallet_capacity": 46, "rate": Decimal("14000.00")},
    {"origin": "PLAS", "destination": "GENSAN", "pallet_capacity": 36, "rate": Decimal("11000.00")},
    {"origin": "PLAS", "destination": "GENSAN", "pallet_capacity": 46, "rate": Decimal("14000.00")},
    {"origin": "PLAS", "destination": "DAV2", "pallet_capacity": 36, "rate": Decimal("1847.00")},
    {"origin": "PLAS", "destination": "DAV2", "pallet_capacity": 46, "rate": Decimal("2200.00")},
    {"origin": "PLAS", "destination": "DAV1", "pallet_capacity": 36, "rate": Decimal("1847.00")},
    {"origin": "PLAS", "destination": "DAV1", "pallet_capacity": 46, "rate": Decimal("2300.00")},
]


def normalize_warehouse_name(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    key = " ".join(text.split())
    return WAREHOUSE_ALIASES.get(key.upper(), WAREHOUSE_ALIASES.get(key.title(), WAREHOUSE_ALIASES.get(key)))


def canonical_warehouse_code(value: Any) -> str | None:
    code = normalize_warehouse_name(value)
    if code is None:
        return None
    return code.upper()


def _coalesce_text(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _clean_line(value: Any) -> str:
    return " ".join(str(value or "").replace("\n", " ").split())


def _extract_date(text: str, labels: tuple[str, ...]) -> str | None:
    pattern = r"(?i)(?:" + "|".join(re.escape(label) for label in labels) + r")\s*[:\-]?\s*(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|\d{2}-\d{2}-\d{4}|\d{1,2}/\d{1,2}/\d{2,4})"
    match = re.search(pattern, text)
    if not match:
        return None
    value = match.group(1)
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y", "%m-%d-%Y", "%d/%m/%y", "%d-%m-%y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return value


def _extract_time(text: str, labels: tuple[str, ...]) -> str | None:
    pattern = r"(?i)(?:" + "|".join(re.escape(label) for label in labels) + r")\s*[:\-]?\s*(\d{1,2}:\d{2}(?:\s?[AaPpMm])?)"
    match = re.search(pattern, text)
    if not match:
        return None
    value = match.group(1).strip().upper().replace(" ", "")
    if value.endswith("AM") or value.endswith("PM"):
        try:
            return datetime.strptime(value, "%I:%M%p").strftime("%H:%M")
        except ValueError:
            return value.lower()
    try:
        return datetime.strptime(value, "%H:%M").strftime("%H:%M")
    except ValueError:
        try:
            return datetime.strptime(value, "%I:%M").strftime("%H:%M")
        except ValueError:
            return value


def _extract_value(text: str, labels: tuple[str, ...]) -> str | None:
    for label in labels:
        pattern = rf"(?i){re.escape(label)}\s*[:\-]?\s*(.+)"
        match = re.search(pattern, text)
        if match:
            value = _clean_line(match.group(1)).strip(" ,;")
            if value:
                return value
    return None


def extract_manifest_fields(ocr_text: str) -> dict[str, Any]:
    text = "\n".join(str(ocr_text or "").splitlines())
    manifest_no = _coalesce_text(
        _extract_value(text, ("Shipment No.", "Shipment No", "Shipment Number", "Manifest No.", "Manifest Number", "ISM No.", "ISM Number", "ISM NO")),
        re.search(r"(?i)(?:Shipment|ISM|Manifest)[^\n\r]{0,12}(?:No\.?|Number|#)?\s*[:\-]?\s*([A-Z0-9/-]+)", text),
    )
    if isinstance(manifest_no, re.Match):
        manifest_no = manifest_no.group(1)
    manifest_date = _extract_date(text, ("Manifest Date", "Date", "Shipment Date"))
    delivery_date = _extract_date(text, ("Delivery Date", "Del Date"))
    manifest_time = _extract_time(text, ("Manifest Time", "Time", "Loading Time"))
    issuing_plant = _extract_value(text, ("Issuing Plant", "Issue Plant", "Plant"))
    receiving_plant = _extract_value(text, ("Rec. Plant", "Rec Plant", "Receiving Plant", "Receiving Plant:"))
    forwarding_agent = _extract_value(text, ("Forwarding Agent", "Fwd Agent", "Forward Agent"))
    vehicle_plate = _extract_value(text, ("Vehicle Lic. No.", "Vehicle License No.", "Vehicle Lic No", "Vehicle Plate", "Vehicle No."))
    vehicle_type = _extract_value(text, ("Vehicle Type", "Truck Type"))
    time_in = _extract_time(text, ("Time In", "Arrival Time"))
    time_out = _extract_time(text, ("Time Out", "Departure Time"))
    driver_name = _extract_value(text, ("Driver", "Driver Name"))
    if driver_name and driver_name.lower() in {"n/a", "na", "not available"}:
        driver_name = None

    origin = canonical_warehouse_code(issuing_plant) or canonical_warehouse_code(_extract_value(text, ("Origin",)))
    destination = canonical_warehouse_code(receiving_plant) or canonical_warehouse_code(_extract_value(text, ("Destination",)))
    warnings: list[str] = []
    if not manifest_no:
        warnings.append("Manifest number not recognized.")
    if not manifest_date:
        warnings.append("Manifest date not recognized.")
    if not issuing_plant:
        warnings.append("Issuing plant not recognized.")
    if not receiving_plant:
        warnings.append("Receiving plant not recognized.")
    if not vehicle_plate:
        warnings.append("Vehicle plate not recognized.")
    if origin and destination and origin == destination:
        warnings.append("Origin and destination resolved to the same warehouse.")

    return {
        "manifest_number": manifest_no,
        "manifest_date": manifest_date,
        "manifest_time": manifest_time,
        "delivery_date": delivery_date,
        "issuing_plant": issuing_plant,
        "receiving_plant": receiving_plant,
        "forwarding_agent": forwarding_agent,
        "driver_name": driver_name,
        "vehicle_plate": vehicle_plate,
        "vehicle_type": vehicle_type,
        "time_in": time_in,
        "time_out": time_out,
        "origin": origin,
        "destination": destination,
        "status": "draft",
        "warnings": warnings,
    }


def truck_route_rate(origin: Any, destination: Any, pallet_capacity: Any) -> Decimal | None:
    origin_code = canonical_warehouse_code(origin)
    destination_code = canonical_warehouse_code(destination)
    if not origin_code or not destination_code:
        return None
    try:
        capacity = int(pallet_capacity)
    except (TypeError, ValueError):
        return None
    for record in TRUCK_ROUTE_RATE_CONFIG:
        if (
            record["origin"] == origin_code
            and record["destination"] == destination_code
            and record["pallet_capacity"] == capacity
        ):
            return record["rate"]
    return None


def scan_manifest_image(image_bytes: bytes, filename: str | None = None) -> dict[str, Any]:
    if not image_bytes:
        raise ValueError("The selected manifest image is empty.")
    try:
        image = Image.open(BytesIO(image_bytes))
        image.verify()
    except Exception as exc:  # pragma: no cover - Image validation path
        raise ValueError("The selected file is not a valid image.") from exc

    try:
        from paddleocr import PaddleOCR  # type: ignore

        temp_path = f"/tmp/{os.path.basename(filename or 'manifest_scan.png')}"
        with open(temp_path, "wb") as handle:
            handle.write(image_bytes)
        ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        result = ocr.ocr(temp_path, cls=True)
        texts = []
        for item in result or []:
            for line in item:
                if isinstance(line, (list, tuple)) and len(line) >= 2:
                    texts.append(str(line[1][0]))
        text = "\n".join(texts)
        return extract_manifest_fields(text)
    except Exception:
        return extract_manifest_fields("")
