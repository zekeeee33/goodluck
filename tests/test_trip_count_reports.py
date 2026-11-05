import unittest
from io import BytesIO

from openpyxl import load_workbook

from excel_report import build_filtered_trip_excel_report, build_trip_excel_report
from report_branding import REPORT_ADDRESS
from trip_pdf_report import build_trip_pdf_report
from trip_report_utils import (
    completed_trip_records,
    group_trip_records,
    group_trip_records_by_route,
    order_trip_records,
)


def trip(trip_count, *, driver="Driver A", origin="Origin", destination="Destination"):
    return {
        "id": trip_count + 100,
        "trip_count": trip_count,
        "status": "completed",
        "trip_date": "2026-01-01",
        "shipment_date": "2026-01-01",
        "driver_name": driver,
        "truck_plate": "TRUCK-1",
        "truck_plate_number": "TRUCK-1",
        "trailer_plate": "TRAILER-1",
        "trailer_plate_number": "TRAILER-1",
        "origin": origin,
        "destination": destination,
        "route": f"{origin} to {destination}",
        "route_number": 1,
        "route_pair": f"{origin}-{destination}",
        "trip_revenue": 100,
    }


class TripCountReportTests(unittest.TestCase):
    def setUp(self):
        self.trips = [
            trip(3, driver="Driver A"),
            trip(1, driver="Driver B"),
            trip(2, driver="Driver A"),
        ]

    def test_trip_records_and_groups_follow_trip_count(self):
        self.assertEqual(
            [item["trip_count"] for item in order_trip_records(self.trips)],
            [1, 2, 3],
        )
        self.assertEqual(
            [item["trip_count"] for item in completed_trip_records(self.trips)],
            [1, 2, 3],
        )
        driver_groups = dict(group_trip_records(self.trips, "driver"))
        self.assertEqual(
            [item["trip_count"] for item in driver_groups["Driver A"]],
            [2, 3],
        )
        route_groups = group_trip_records_by_route(self.trips)
        self.assertEqual(
            [item["trip_count"] for item in route_groups[0]["trips"]],
            [1, 2, 3],
        )

    def test_trip_history_excel_uses_numeric_count_and_chronological_rows(self):
        workbook = load_workbook(build_trip_excel_report(self.trips))
        worksheet = workbook["Trip History"]
        self.assertEqual(worksheet["B1"].value, "Fleet Management System - Trip History")
        self.assertEqual(worksheet["B2"].value, REPORT_ADDRESS)
        self.assertEqual(len(worksheet._images), 1)
        self.assertEqual(worksheet._images[0].anchor._from.col, 0)
        self.assertEqual(worksheet._images[0].anchor._from.row, 0)
        self.assertEqual(worksheet._images[0].anchor.ext.cx, 96 * 9525)
        self.assertEqual(worksheet["A4"].value, "Trip Count")
        self.assertEqual(
            [worksheet.cell(row=row, column=1).value for row in range(5, 8)],
            [1, 2, 3],
        )
        self.assertTrue(all(
            isinstance(worksheet.cell(row=row, column=1).value, int)
            for row in range(5, 8)
        ))

    def test_filtered_excel_details_include_trip_count(self):
        workbook = load_workbook(build_filtered_trip_excel_report(
            self.trips,
            {"title": "All Trips", "generated_at": "", "filter_summary": "All trips"},
        ))
        self.assertTrue(all(
            worksheet["B2"].value == REPORT_ADDRESS
            and len(worksheet._images) == 1
            for worksheet in workbook.worksheets
        ))
        worksheet = workbook["Route Details"]
        self.assertEqual(worksheet["B1"].value, "Detailed Route Records")
        self.assertEqual(worksheet["B6"].value, "Origin")
        self.assertEqual(worksheet["C6"].value, "Destination")
        self.assertEqual(worksheet["D6"].value, "Trip Count")
        self.assertEqual(
            [worksheet.cell(row=row, column=4).value for row in range(7, 10)],
            [1, 2, 3],
        )

    def test_trip_pdf_export_is_generated_with_trip_count_field(self):
        pdf = build_trip_pdf_report(
            self.trips,
            {"title": "All Trips", "generated_at": "", "filter_summary": "All trips"},
        )
        self.assertIsInstance(pdf, BytesIO)
        self.assertTrue(pdf.getvalue().startswith(b"%PDF-"))


if __name__ == "__main__":
    unittest.main()
