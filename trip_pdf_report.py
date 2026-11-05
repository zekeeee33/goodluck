from __future__ import annotations

from html import escape
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from report_branding import REPORT_ADDRESS, report_logo_path
from trip_report_utils import (
    TRIP_REPORT_FIELDS,
    completed_trip_records,
    group_trip_records_by_driver,
    group_trip_records_by_route,
    summarize_trip_records,
)

ROUTE_DETAIL_FIELDS = tuple(
    (field, label)
    for field, label in TRIP_REPORT_FIELDS
    if field not in {"origin", "destination"}
)


def build_trip_pdf_report(
    trips: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> BytesIO:
    trips = completed_trip_records(trips)
    output = BytesIO()
    page_width, page_height = landscape(A4)
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=7 * mm,
        leftMargin=7 * mm,
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
        "TripReportCell", parent=styles["Normal"],         fontSize=6, leading=7,
        wordWrap="CJK",
    )
    header_style = ParagraphStyle(
        "TripReportHeader", parent=cell_style, fontName="Helvetica-Bold",
        textColor=colors.white, alignment=TA_CENTER,
    )
    summary = summarize_trip_records(trips)
    grouping = str(metadata.get("group_by") or metadata.get("report_type") or "all")
    title = str(metadata.get("title") or "Trip Report")
    available_width = page_width - 14 * mm
    average_revenue = summary["average_revenue_per_trip"]
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
                Paragraph("TOTAL GROSS TRIP REVENUE", summary_label_style),
                Paragraph("AVERAGE GROSS REVENUE / VALID TRIP", summary_label_style),
            ], [
                Paragraph(f"{summary['total_trips']:,}", summary_value_style),
                Paragraph(f"{len(routes):,}", summary_value_style),
                Paragraph(f"{len(drivers):,}", summary_value_style),
                Paragraph(
                    f"PHP {summary['total_revenue']:,.2f}"
                    if summary["revenue_trip_count"] else "—",
                    summary_value_style,
                ),
                Paragraph(
                    f"PHP {average_revenue:,.2f}" if average_revenue is not None else "—",
                    summary_value_style,
                ),
            ]],
            colWidths=[available_width / 5] * 5,
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
    natural_widths = [12, 21, 30, 25, 20, 26, 26, 20, 18, 15, 15, 30]
    scale = available_width / sum(natural_widths)
    table_widths = [width * scale for width in natural_widths]
    route_detail_natural_widths = [
        width
        for (field, _), width in zip(TRIP_REPORT_FIELDS, natural_widths)
        if field not in {"origin", "destination"}
    ]
    route_detail_natural_width_total = sum(route_detail_natural_widths)
    route_detail_widths = [
        available_width * 0.08,
        available_width * 0.22,
        available_width * 0.22,
    ] + [
        available_width * 0.48 * width / route_detail_natural_width_total
        for (field, _), width in zip(TRIP_REPORT_FIELDS, natural_widths)
        if field not in {"origin", "destination"}
    ]

    route_summary_rows = [[
        Paragraph("Route", header_style),
        Paragraph("Origin", header_style),
        Paragraph("Destination", header_style),
        Paragraph("Total Trips", header_style),
        Paragraph("Total Revenue", header_style),
    ]]
    for route in routes:
        route_totals = summarize_trip_records(route["trips"])
        route_summary_rows.append([
            Paragraph(escape(route["label"]), cell_style),
            Paragraph(escape(route["origin"]), cell_style),
            Paragraph(escape(route["destination"]), cell_style),
            Paragraph(str(route_totals["total_trips"]), cell_style),
            Paragraph(
                f"PHP {route_totals['total_revenue']:,.2f}"
                if route_totals["revenue_trip_count"] else "—",
                cell_style,
            ),
        ])
    if grouping != "driver":
        story.extend([
            Paragraph("Route Summary", group_style),
            Table(
                route_summary_rows,
                colWidths=[
                    available_width * 0.12,
                    available_width * 0.24,
                    available_width * 0.24,
                    available_width * 0.14,
                    available_width * 0.26,
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
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
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
                Paragraph("Total Revenue", header_style),
            ]]
            for route in driver_routes:
                route_summary = summarize_trip_records(route["trips"])
                movement_rows.append([
                    Paragraph(escape(route["label"]), cell_style),
                    Paragraph(escape(route["origin"]), cell_style),
                    Paragraph(escape(route["destination"]), cell_style),
                    Paragraph(str(route_summary["total_trips"]), cell_style),
                    Paragraph(
                        f"PHP {route_summary['total_revenue']:,.2f}"
                        if route_summary["revenue_trip_count"] else "—",
                        cell_style,
                    ),
                ])
            story.extend([
                Paragraph("Movement Summary", group_style),
                Table(
                    movement_rows,
                    colWidths=[
                        available_width * 0.12,
                        available_width * 0.24,
                        available_width * 0.24,
                        available_width * 0.14,
                        available_width * 0.26,
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
        for route in routes:
            group_trips = route["trips"]
            story.append(Paragraph(
                f"{escape(route['label'])} | Origin: {escape(route['origin'])} | "
                f"Destination: {escape(route['destination'])}",
                group_style,
            ))
            story.append(trip_table(group_trips))
            story.append(Spacer(1, 2 * mm))

    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        f"Overall total: {summary['total_trips']} trips | "
        "Gross trip revenue: "
        + (
            f"PHP {summary['total_revenue']:,.2f}"
            if summary["revenue_trip_count"] else "—"
        ),
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
