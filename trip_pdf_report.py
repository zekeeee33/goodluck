from __future__ import annotations

from decimal import Decimal
from html import escape
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    LongTable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from trip_report_utils import (
    TRIP_REPORT_FIELDS,
    completed_trip_records,
    group_trip_records_by_driver,
    group_trip_records_by_route,
    summarize_trip_records,
)


def build_trip_pdf_report(
    trips: list[dict[str, Any]],
    metadata: dict[str, Any],
) -> BytesIO:
    trips = completed_trip_records(trips)
    output = BytesIO()
    page_width, _ = landscape(A3)
    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A3),
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=12 * mm,
        bottomMargin=16 * mm,
        title=str(metadata.get("title") or "Trip Report"),
        author="Fleet Management System",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TripReportTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=17, leading=20, textColor=colors.HexColor("#17365D"),
        alignment=TA_LEFT, spaceAfter=2 * mm,
    )
    small_style = ParagraphStyle(
        "TripReportSmall", parent=styles["Normal"], fontSize=8, leading=11,
        textColor=colors.HexColor("#475569"),
    )
    group_style = ParagraphStyle(
        "TripReportGroup", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=10, leading=13, textColor=colors.HexColor("#17365D"),
        spaceBefore=3 * mm, spaceAfter=2 * mm, keepWithNext=True,
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
        "TripReportCell", parent=styles["Normal"], fontSize=5.5, leading=7,
        wordWrap="CJK",
    )
    header_style = ParagraphStyle(
        "TripReportHeader", parent=cell_style, fontName="Helvetica-Bold",
        textColor=colors.white, alignment=TA_CENTER,
    )
    summary = summarize_trip_records(trips)
    grouping = str(metadata.get("group_by") or metadata.get("report_type") or "all")
    title = str(metadata.get("title") or "Trip Report")
    available_width = page_width - 20 * mm
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
                Paragraph("TOTAL DISTANCE", summary_label_style),
                Paragraph("TOTAL GROSS TRIP REVENUE", summary_label_style),
                Paragraph("AVERAGE GROSS REVENUE / VALID TRIP", summary_label_style),
            ], [
                Paragraph(f"{summary['total_trips']:,}", summary_value_style),
                Paragraph(f"{len(routes):,}", summary_value_style),
                Paragraph(f"{len(drivers):,}", summary_value_style),
                Paragraph(
                    f"{summary['total_distance']:,.1f} km "
                    f"({summary['distance_trip_count']} measured)",
                    summary_value_style,
                ),
                Paragraph(
                    f"PHP {summary['total_revenue']:,.2f}"
                    if summary["revenue_trip_count"] else "N/A",
                    summary_value_style,
                ),
                Paragraph(
                    f"PHP {average_revenue:,.2f}" if average_revenue is not None else "N/A",
                    summary_value_style,
                ),
            ]],
            colWidths=[available_width / 6] * 6,
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

    natural_widths = [
        15, 20, 24, 19, 19, 23, 23, 18, 18, 17, 21, 19, 18, 15, 15, 27, 28, 23,
    ]
    scale = available_width / sum(natural_widths)
    table_widths = [width * scale for width in natural_widths]
    headers = [label for _, label in TRIP_REPORT_FIELDS]

    route_summary_rows = [[
        Paragraph("Route", header_style),
        Paragraph("Route Description", header_style),
        Paragraph("Total Trips", header_style),
        Paragraph("Total Revenue", header_style),
    ]]
    for route in routes:
        route_totals = summarize_trip_records(route["trips"])
        route_summary_rows.append([
            Paragraph(escape(route["label"]), cell_style),
            Paragraph(
                escape(f"{route['origin']} → {route['destination']}"),
                cell_style,
            ),
            Paragraph(str(route_totals["total_trips"]), cell_style),
            Paragraph(
                f"PHP {route_totals['total_revenue']:,.2f}"
                if route_totals["revenue_trip_count"] else "N/A",
                cell_style,
            ),
        ])
    story.extend([
        Paragraph("Route Summary", group_style),
        Table(
            route_summary_rows,
            colWidths=[
                available_width * 0.18,
                available_width * 0.48,
                available_width * 0.14,
                available_width * 0.20,
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

    def trip_table(group_trips: list[dict[str, Any]]) -> LongTable:
        table_rows = [[Paragraph(escape(label), header_style) for label in headers]]
        for trip in group_trips:
            row = []
            for field, _ in TRIP_REPORT_FIELDS:
                value = trip.get(field)
                if field == "trip_revenue" and value is not None:
                    value = f"PHP {Decimal(str(value)):,.2f}"
                elif field in {"start_odometer", "end_odometer", "distance"} and value is not None:
                    value = f"{Decimal(str(value)):,.1f}"
                row.append(Paragraph(
                    escape(str(value if value not in (None, "") else "-")),
                    cell_style,
                ))
            table_rows.append(row)
        report_table = LongTable(
            table_rows,
            colWidths=table_widths,
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

    for route in routes:
        group_trips = route["trips"]
        group_summary = summarize_trip_records(group_trips)
        story.append(Paragraph(
            f"{escape(route['label'])}: "
            f"{escape(route['origin'])} → {escape(route['destination'])} | "
            f"{group_summary['total_trips']} "
            f"{'trip' if group_summary['total_trips'] == 1 else 'trips'} | "
            "Gross revenue: "
            + (
                f"PHP {group_summary['total_revenue']:,.2f}"
                if group_summary["revenue_trip_count"] else "N/A"
            ),
            group_style,
        ))
        story.append(trip_table(group_trips))
        story.append(Spacer(1, 2 * mm))

    if grouping == "driver":
        story.append(Paragraph("Per-Driver Route Breakdown", group_style))
        for driver_name, driver_trips in drivers:
            driver_routes = group_trip_records_by_route(driver_trips)
            driver_summary = summarize_trip_records(driver_trips)
            story.append(Paragraph(
                f"Driver: {escape(driver_name)} | "
                f"{driver_summary['total_trips']} trips | "
                f"{len(driver_routes)} routes | "
                "Gross revenue: "
                + (
                    f"PHP {driver_summary['total_revenue']:,.2f}"
                    if driver_summary["revenue_trip_count"] else "N/A"
                ),
                group_style,
            ))
            for route in driver_routes:
                route_summary = summarize_trip_records(route["trips"])
                story.append(Paragraph(
                    f"{escape(route['label'])}: "
                    f"{escape(route['origin'])} → {escape(route['destination'])} | "
                    f"{route_summary['total_trips']} trips | "
                    "Gross revenue: "
                    + (
                        f"PHP {route_summary['total_revenue']:,.2f}"
                        if route_summary["revenue_trip_count"] else "N/A"
                    ),
                    small_style,
                ))
                story.append(trip_table(route["trips"]))
                story.append(Spacer(1, 2 * mm))

    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        f"Overall total: {summary['total_trips']} trips | "
        f"{summary['total_distance']:,.1f} km | "
        "Gross trip revenue: "
        + (
            f"PHP {summary['total_revenue']:,.2f}"
            if summary["revenue_trip_count"] else "N/A"
        ),
        group_style,
    ))

    def draw_page(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(10 * mm, 8 * mm, "Fleet Management System - Trip Report")
        canvas.drawRightString(page_width - 10 * mm, 8 * mm, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    output.seek(0)
    return output
