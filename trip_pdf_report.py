from __future__ import annotations

from html import escape
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from report_branding import REPORT_ADDRESS, report_logo_path
from trip_report_utils import (
    TRIP_REPORT_FIELDS,
    group_trip_records_by_driver,
    group_trip_records_by_route,
    order_trip_records,
    summarize_trip_records,
)

ROUTE_DETAIL_FIELDS = tuple(
    (field, label)
    for field, label in TRIP_REPORT_FIELDS
    if field not in {"origin", "destination"}
)

SHORT_ROUTE_LOCATIONS = {
    "davao bottling plant 1": "DAV1",
    "davao bottling plant 2": "DAV2",
    "gensan distribution center": "GENSAN",
    "plas astorga": "PLAS",
}


def _short_route_location(location: str) -> str:
    normalized = " ".join(location.split()).casefold()
    return SHORT_ROUTE_LOCATIONS.get(normalized, location)


def build_trip_pdf_report(
    trips: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> BytesIO:
    trips = order_trip_records(trips)
    output = BytesIO()
    page_width, page_height = landscape(A3)
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A3),
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=30 * mm,
        bottomMargin=9 * mm,
        title=str(metadata.get("title") or "Trip Report"),
        author="Fleet Management System",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TripReportTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=14, leading=16, textColor=colors.HexColor("#17365D"),
        alignment=TA_LEFT, spaceAfter=1 * mm,
    )
    small_style = ParagraphStyle(
        "TripReportSmall", parent=styles["Normal"],         fontSize=7, leading=8,
        textColor=colors.HexColor("#475569"),
    )
    group_style = ParagraphStyle(
        "TripReportGroup", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=9, leading=10, textColor=colors.HexColor("#17365D"),
        spaceBefore=2 * mm, spaceAfter=1 * mm, keepWithNext=True,
    )
    summary_label_style = ParagraphStyle(
        "TripReportSummaryLabel", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=7, leading=9, textColor=colors.white, alignment=TA_CENTER,
    )
    summary_value_style = ParagraphStyle(
        "TripReportSummaryValue", parent=styles["Normal"], fontName="Helvetica-Bold",
        fontSize=11, leading=13, textColor=colors.HexColor("#17365D"),
        alignment=TA_CENTER,
    )
    cell_style = ParagraphStyle(
        "TripReportCell", parent=styles["Normal"], fontSize=7.5, leading=9,
        wordWrap="CJK",
    )
    header_style = ParagraphStyle(
        "TripReportHeader", parent=cell_style, fontName="Helvetica-Bold",
        textColor=colors.white, alignment=TA_CENTER,
    )
    matrix_route_style = ParagraphStyle(
        "TripReportMatrixRoute", parent=header_style,
        fontSize=6.5, leading=7.5,
        textColor=colors.HexColor("#172033"),
    )
    compact_cell_style = ParagraphStyle(
        "TripReportCompactCell", parent=cell_style,
        fontSize=6.5, leading=7.5,
    )
    summary = summarize_trip_records(trips)
    grouping = str(metadata.get("group_by") or metadata.get("report_type") or "all")
    title = str(metadata.get("title") or "Trip Report")
    available_width = page_width - 14 * mm
    routes = group_trip_records_by_route(trips)
    drivers = group_trip_records_by_driver(trips)
    story = [
        Paragraph(escape(title), title_style),
        Paragraph(
            f"Generated: {escape(str(metadata.get('generated_at', '')))}",
            small_style,
        ),
        Paragraph(
            f"Filters: {escape(str(metadata.get('filter_summary') or 'All trips'))}",
            small_style,
        ),
        Table(
            [[
                Paragraph("COMPLETED TRIPS", summary_label_style),
                Paragraph("UNIQUE ROUTES", summary_label_style),
                Paragraph("DRIVERS", summary_label_style),
            ], [
                Paragraph(f"{summary['total_trips']:,}", summary_value_style),
                Paragraph(f"{len(routes):,}", summary_value_style),
                Paragraph(f"{len(drivers):,}", summary_value_style),
            ]],
            colWidths=[available_width / 3] * 3,
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#EAF1F8")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#CBD5E1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]),
        ),
        Spacer(1, 3 * mm),
    ]
    detail_column_weights = {
        "route": 7,
        "origin": 13,
        "destination": 13,
        "trip_count": 5,
        "trip_date": 8,
        "driver_name": 11,
        "truck_plate": 8,
        "trailer_plate": 7,
        "shipment_date": 8,
        "ism_no": 8,
        "time_in": 5,
        "time_out": 5,
        "load_details": 9,
    }

    def detail_column_widths(fields: tuple[tuple[str, str], ...], include_route: bool) -> list[float]:
        column_fields = (
            (["route", "origin", "destination"] if include_route else [])
            + [field for field, _ in fields]
        )
        total_weight = sum(detail_column_weights[field] for field in column_fields)
        return [
            available_width * detail_column_weights[field] / total_weight
            for field in column_fields
        ]

    table_widths = detail_column_widths(TRIP_REPORT_FIELDS, False)
    route_detail_widths = detail_column_widths(ROUTE_DETAIL_FIELDS, True)

    route_summary_rows = [[
        Paragraph("Route", header_style),
        Paragraph("Origin", header_style),
        Paragraph("Destination", header_style),
        Paragraph("Total Trips", header_style),
    ]]
    for route in routes:
        route_totals = summarize_trip_records(route["trips"])
        route_summary_rows.append([
            Paragraph(escape(route["label"]), compact_cell_style),
            Paragraph(escape(_short_route_location(route["origin"])), compact_cell_style),
            Paragraph(escape(_short_route_location(route["destination"])), compact_cell_style),
            Paragraph(str(route_totals["total_trips"]), compact_cell_style),
        ])
    if grouping != "driver":
        story.extend([
            Paragraph("Route Summary", group_style),
            Table(
                route_summary_rows,
                colWidths=[25 * mm, 42 * mm, 42 * mm, 25 * mm],
                repeatRows=1,
                style=TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                        colors.white, colors.HexColor("#EAF1F8"),
                    ]),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2.5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2.5),
                    ("TOPPADDING", (0, 0), (-1, -1), 1),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
                ]),
            ),
            Spacer(1, 3 * mm),
        ])

    if routes:
        story.append(Paragraph("Summary Per Driver", group_style))
        legend_parts = [
            f"{escape(route['label'])}: {_short_route_location(route['origin'])} → {_short_route_location(route['destination'])}"
            for route in routes
        ]
        legend_style = ParagraphStyle(
            "TripReportRouteLegend", parent=small_style,
            fontSize=6.5, leading=7.5,
        )
        story.append(Paragraph("<b>Route Legend:</b> " + " &nbsp; | &nbsp; ".join(legend_parts), legend_style))
        story.append(Spacer(1, 1 * mm))
        matrix_rows = [[
            Paragraph("Driver", header_style),
            *[Paragraph(escape(route["label"]), header_style) for route in routes],
            Paragraph("No. of Trips", header_style),
        ]]
        for driver_name, driver_trips in drivers:
            driver_trip_ids = {id(trip) for trip in driver_trips}
            route_counts = [
                sum(id(trip) in driver_trip_ids for trip in route["trips"])
                for route in routes
            ]
            matrix_rows.append([
                Paragraph(escape(driver_name), compact_cell_style),
                *[Paragraph(str(count), compact_cell_style) for count in route_counts],
                Paragraph(str(len(driver_trips)), compact_cell_style),
            ])

        route_columns_width = max(
            8 * mm,
            (available_width - 42 * mm - 22 * mm) / max(len(routes), 1),
        )
        matrix_column_widths = [
            42 * mm,
            *[route_columns_width for _ in routes],
            22 * mm,
        ]
        matrix_table = Table(
            matrix_rows,
            colWidths=matrix_column_widths,
            repeatRows=1,
            hAlign="LEFT",
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                    colors.white, colors.HexColor("#E2E8F0"),
                ]),
                ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#64748B")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 1), (-1, -1), "CENTER"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1.5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1.5),
                ("TOPPADDING", (0, 0), (-1, -1), 1.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
            ]),
        )
        story.append(matrix_table)

    def trip_table(
        group_trips: list[dict[str, Any]],
        include_route: bool = False,
    ) -> LongTable:
        route_lookup = {
            id(trip): route
            for route in routes
            for trip in route["trips"]
        }
        fields = ROUTE_DETAIL_FIELDS if include_route else TRIP_REPORT_FIELDS
        table_headers = (
            ["Route", "Origin", "Destination"] if include_route else []
        ) + [label for _, label in fields]
        table_rows = [[
            Paragraph(escape(label), header_style) for label in table_headers
        ]]
        for trip in group_trips:
            row = []
            if include_route:
                route = route_lookup[id(trip)]
                row.extend([
                    Paragraph(escape(route["label"]), cell_style),
                    Paragraph(escape(route["origin"]), cell_style),
                    Paragraph(escape(route["destination"]), cell_style),
                ])
            for field, _ in fields:
                value = trip.get(field)
                row.append(Paragraph(
                    escape(str(value if value not in (None, "") else "-")),
                    cell_style,
                ))
            table_rows.append(row)
        report_table = LongTable(
            table_rows,
            colWidths=route_detail_widths if include_route else table_widths,
            repeatRows=1,
            splitByRow=1,
            hAlign="LEFT",
        )
        report_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                colors.white, colors.HexColor("#EAF1F8"),
            ]),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
        ]))
        return report_table

    if grouping == "driver":
        story.append(Paragraph("Per-Driver Trips and Movement", group_style))
        for driver_name, driver_trips in drivers:
            driver_trip_ids = {id(trip) for trip in driver_trips}
            driver_routes = [
                {
                    **route,
                    "trips": [
                        trip for trip in route["trips"]
                        if id(trip) in driver_trip_ids
                    ],
                }
                for route in routes
                if any(id(trip) in driver_trip_ids for trip in route["trips"])
            ]
            driver_summary = summarize_trip_records(driver_trips)
            story.append(Paragraph(
                f"Driver: {escape(driver_name)} | {driver_summary['total_trips']} trips",
                group_style,
            ))
            story.append(trip_table(driver_trips, include_route=True))
            movement_rows = [[
                Paragraph("Route", header_style),
                Paragraph("Origin", header_style),
                Paragraph("Destination", header_style),
                Paragraph("Total Trips", header_style),
            ]]
            for route in driver_routes:
                route_summary = summarize_trip_records(route["trips"])
                movement_rows.append([
                    Paragraph(escape(route["label"]), cell_style),
                    Paragraph(escape(route["origin"]), cell_style),
                    Paragraph(escape(route["destination"]), cell_style),
                    Paragraph(str(route_summary["total_trips"]), cell_style),
                ])
            story.extend([
                Paragraph("Movement Summary", group_style),
                Table(
                    movement_rows,
                    colWidths=[
                        available_width * 0.14,
                        available_width * 0.29,
                        available_width * 0.29,
                        available_width * 0.28,
                    ],
                    repeatRows=1,
                    style=TableStyle([
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E78")),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                            colors.white, colors.HexColor("#EAF1F8"),
                        ]),
                        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]),
                ),
                Spacer(1, 3 * mm),
            ])
    else:
        if routes:
            story.append(PageBreak())
        story.append(trip_table(trips, include_route=True))

    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        f"Overall total: {summary['total_trips']} trips",
        group_style,
    ))

    def draw_page(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        logo_width, logo_height = ImageReader(report_logo_path()).getSize()
        rendered_logo_width = 42 * mm
        canvas.drawImage(
            report_logo_path(),
            7 * mm,
            page_height - 27 * mm,
            width=rendered_logo_width,
            height=rendered_logo_width * logo_height / logo_width,
            preserveAspectRatio=True,
            mask="auto",
        )
        canvas.setFont("Helvetica", 9)
        canvas.setFillColor(colors.HexColor("#475569"))
        canvas.drawRightString(
            page_width - 7 * mm,
            page_height - 14 * mm,
            REPORT_ADDRESS,
        )
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(7 * mm, 6 * mm, "Fleet Management System - Trip Report")
        canvas.drawRightString(page_width - 7 * mm, 6 * mm, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    output.seek(0)
    return output
