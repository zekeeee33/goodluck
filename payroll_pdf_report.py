from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from html import escape
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
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

_NAVY = colors.HexColor("#17365D")
_BLUE = colors.HexColor("#1F4E78")
_SLATE = colors.HexColor("#475569")
_LIGHT = colors.HexColor("#F1F5F9")
_BORDER = colors.HexColor("#CBD5E1")


def _money(value: Any) -> str:
    amount = Decimal(str(value or 0))
    return f"PHP {amount:,.2f}"


def _text(value: Any, empty: str = "—") -> str:
    return escape(str(value)) if value not in (None, "") else empty


def build_payroll_pdf_report(
    report: dict[str, Any],
    trips: list[dict[str, Any]],
    drivers: list[dict[str, Any]],
    start_date: str,
    end_date: str,
    filters: dict[str, str],
    *,
    payroll_number: str | int | None = None,
) -> BytesIO:
    payroll_number = str(payroll_number or f"X{uuid.uuid4().hex.upper()}")
    output = BytesIO()
    page_width, page_height = letter
    document = SimpleDocTemplate(
        output,
        pagesize=letter,
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=29 * mm,
        bottomMargin=12 * mm,
        title=f"Payroll report {start_date} to {end_date}",
        author="Fleet Management System",
    )
    available_width = page_width - 24 * mm
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "PayrollTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=20,
        textColor=_NAVY,
        alignment=TA_LEFT,
        spaceAfter=2 * mm,
    )
    heading_style = ParagraphStyle(
        "PayrollHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=13,
        textColor=_NAVY,
        spaceBefore=2 * mm,
        spaceAfter=2 * mm,
        keepWithNext=True,
    )
    body_style = ParagraphStyle(
        "PayrollBody",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#172033"),
    )
    small_style = ParagraphStyle(
        "PayrollSmall",
        parent=body_style,
        fontSize=7,
        leading=8.5,
        textColor=_SLATE,
    )
    header_style = ParagraphStyle(
        "PayrollTableHeader",
        parent=body_style,
        fontName="Helvetica-Bold",
        textColor=colors.white,
        alignment=TA_CENTER,
    )
    right_style = ParagraphStyle(
        "PayrollRight",
        parent=body_style,
        alignment=TA_RIGHT,
    )
    small_right_style = ParagraphStyle(
        "PayrollSmallRight",
        parent=small_style,
        alignment=TA_RIGHT,
    )
    period = f"Pay period: {start_date} to {end_date} | Status: {str(report.get('status', 'draft')).title()}"
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        if start.year == end.year and start.month == end.month:
            short_period = (
                f"{start.strftime('%b').upper()} {start.day}–{end.day}, {end.year}"
            )
        elif start.year == end.year:
            short_period = (
                f"{start.strftime('%b').upper()} {start.day}–"
                f"{end.strftime('%b').upper()} {end.day}, {end.year}"
            )
        else:
            short_period = (
                f"{start.strftime('%b').upper()} {start.day}, {start.year}–"
                f"{end.strftime('%b').upper()} {end.day}, {end.year}"
            )
    except ValueError:
        short_period = f"{start_date} to {end_date}"
    active_filters = [
        f"{key.replace('_', ' ').title()}: {value}"
        for key, value in filters.items()
        if value
    ]
    filter_summary = "Active filters: " + ("; ".join(active_filters) if active_filters else "None")

    def cell(value: Any, style: ParagraphStyle = body_style, empty: str = "—") -> Paragraph:
        return Paragraph(_text(value, empty), style)

    def make_table(
        headers: list[str],
        rows: list[list[Any]],
        widths: list[float],
        empty_message: str,
        repeated_heading: Paragraph | None = None,
    ) -> LongTable:
        table_rows: list[list[Any]] = []
        if repeated_heading:
            table_rows.append([
                repeated_heading,
                *[Paragraph("", body_style) for _ in headers[1:]],
            ])
        table_rows.append([Paragraph(escape(header), header_style) for header in headers])
        if rows:
            table_rows.extend(rows)
        else:
            table_rows.append([
                Paragraph(escape(empty_message), small_style),
                *[Paragraph("", body_style) for _ in headers[1:]],
            ])
        header_rows = 2 if repeated_heading else 1
        table_style = [
            ("BACKGROUND", (0, 0), (-1, header_rows - 1), _BLUE),
            ("ROWBACKGROUNDS", (0, header_rows), (-1, -1), [colors.white, _LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.35, _BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]
        if repeated_heading:
            table_style.append(("SPAN", (0, 0), (-1, 0)))
        return LongTable(
            table_rows,
            colWidths=widths,
            repeatRows=header_rows,
            hAlign="LEFT",
            style=TableStyle(table_style),
        )

    def add_section(story: list[Any], title: str, table: LongTable) -> None:
        story.extend([Paragraph(escape(title), heading_style), table])

    def currency_total(records: list[dict[str, Any]], field: str) -> Decimal:
        return sum(
            (Decimal(str(record.get(field) or 0)) for record in records),
            Decimal("0.00"),
        )

    def trip_key(trip: dict[str, Any]) -> str:
        return str(trip.get("driver_key") or f"id:{trip.get('driver_id')}")

    summary_drivers: list[dict[str, Any]] = []
    for driver in drivers:
        driver_key = driver.get("driver_key") or f"id:{driver.get('driver_id')}"
        eligible_count = sum(
            bool(trip.get("eligible")) and trip_key(trip) == driver_key
            for trip in trips
        )
        summary_drivers.append({**driver, "visible_trip_count": eligible_count})

    eligible_trip_count = sum(bool(trip.get("eligible")) for trip in trips)
    total_net = sum(
        (
            Decimal(str(
                driver.get("final_net_pay")
                if driver.get("final_net_pay") is not None
                else max(Decimal(str(driver.get("net_before_overdraft") or 0)), Decimal("0"))
            ))
            for driver in summary_drivers
        ),
        Decimal("0.00"),
    )
    document_count = len(summary_drivers)
    statement_widths = [
        available_width * weight / 100
        for weight in (17, 18, 6, 11, 10, 9, 10, 10, 9)
    ]
    statement_rows = []
    for index, driver in enumerate(summary_drivers, start=1):
        document_number = f"PAY-{payroll_number}-DOC-{index:03d}"
        statement_rows.append([
            cell(driver.get("driver_name")),
            cell(document_number, small_style),
            cell(driver["visible_trip_count"], small_right_style),
            cell(_money(driver.get("gross_pay")), small_right_style),
            cell(_money(driver.get("cash_advances")), small_right_style),
            cell(_money(driver.get("overdraft_deduction")), small_right_style),
            cell(_money(
                driver.get("remaining_overdraft")
                if driver.get("remaining_overdraft") is not None
                else driver.get("overdraft_balance")
            ), small_right_style),
            cell(_money(
                driver.get("final_net_pay")
                if driver.get("final_net_pay") is not None
                else max(Decimal(str(driver.get("net_before_overdraft") or 0)), Decimal("0"))
            ), small_right_style),
            cell(_money(driver.get("remaining_amount_due")), small_right_style),
        ])

    story: list[Any] = [
        Paragraph(f"Payroll Report #{_text(payroll_number)}", title_style),
        Paragraph(escape(period), body_style),
        Paragraph(escape(filter_summary), small_style),
        Spacer(1, 4 * mm),
    ]
    totals_data = [
        [
            Paragraph("DRIVERS", header_style),
            Paragraph("ELIGIBLE TRIPS", header_style),
            Paragraph("GROSS PAYROLL", header_style),
            Paragraph("CASH ADVANCES", header_style),
            Paragraph("OVERDRAFT BALANCE", header_style),
            Paragraph("NET PAYABLE", header_style),
        ],
        [
            str(len(summary_drivers)),
            f"{eligible_trip_count:,}",
            _money(currency_total(summary_drivers, "gross_pay")),
            _money(currency_total(summary_drivers, "cash_advances")),
            _money(sum(
                (
                    Decimal(str(
                        driver.get("remaining_overdraft")
                        if driver.get("remaining_overdraft") is not None
                        else driver.get("overdraft_balance") or 0
                    ))
                    for driver in summary_drivers
                ),
                Decimal("0.00"),
            )),
            _money(total_net),
        ],
    ]
    totals_table = Table(
        totals_data,
        colWidths=[available_width / 6] * 6,
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _BLUE),
            ("BACKGROUND", (0, 1), (-1, 1), _LIGHT),
            ("BOX", (0, 0), (-1, -1), 0.5, _BORDER),
            ("INNERGRID", (0, 0), (-1, -1), 0.35, _BORDER),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]),
    )
    story.extend([
        Paragraph("Payroll totals", heading_style),
        totals_table,
        Spacer(1, 3 * mm),
    ])
    add_section(
        story,
        "Driver payroll statements",
        make_table(
            [
                "Driver", "Document No.", "Trips", "Gross", "Advances",
                "OD Deduction", "Outstanding OD", "Final net pay", "Amount due",
            ],
            statement_rows,
            statement_widths,
            "No drivers match the selected payroll filters.",
        ),
    )

    related_driver_ids = {str(driver.get("driver_id")) for driver in summary_drivers}
    name_by_driver_id = {
        str(driver.get("driver_id")): driver.get("driver_name")
        for driver in summary_drivers
    }
    advances = [
        advance for advance in report.get("cash_advances", [])
        if str(advance.get("driver_id")) in related_driver_ids
    ]
    advances.sort(key=lambda advance: (str(advance.get("advance_date") or ""), str(advance.get("driver_id") or "")))
    add_section(
        story,
        "Cash advances",
        make_table(
            ["Driver", "Date", "Amount", "Reference", "Remarks"],
            [[
                cell(name_by_driver_id.get(str(advance.get("driver_id")))),
                cell(advance.get("advance_date")),
                cell(_money(advance.get("amount")), right_style),
                cell(advance.get("reference")),
                cell(advance.get("remarks")),
            ] for advance in advances],
            [available_width * weight / 100 for weight in (20, 14, 15, 20, 31)],
            "No cash advances recorded for the selected drivers.",
        ),
    )

    overdraft_rows = [
        [
            cell(driver.get("driver_name")),
            cell(transaction.get("effective_date")),
            cell(transaction.get("transaction_type")),
            cell(_money(transaction.get("amount")), right_style),
            cell(transaction.get("remarks")),
        ]
        for driver in summary_drivers
        for transaction in driver.get("overdraft_transactions", [])
    ]
    add_section(
        story,
        "Overdraft ledger",
        make_table(
            ["Driver", "Effective date", "Transaction", "Amount", "Remarks"],
            overdraft_rows,
            [available_width * weight / 100 for weight in (20, 16, 20, 15, 29)],
            "No overdraft transactions recorded.",
        ),
    )

    review_trip_headers = [
        "Date", "Driver", "ISM Number", "Origin", "Destination",
        "Trip Allowance", "Truck Rate", "Review",
    ]
    review_trip_widths = [
        available_width * weight / 100 for weight in (10, 15, 14, 12, 12, 12, 12, 13)
    ]
    review_trip_rows = [[
        cell(trip.get("payroll_date")),
        cell(trip.get("driver_name")),
        cell(trip.get("ism_no")),
        cell(trip.get("origin")),
        cell(trip.get("destination")),
        cell(_money(trip.get("rate")), right_style),
        cell(_money(trip.get("truck_route_rate")), right_style),
        cell(trip.get("issue") or "Needs review"),
    ] for trip in report.get("issues", [])]
    add_section(
        story,
        "Trips requiring review",
        make_table(
            review_trip_headers,
            review_trip_rows,
            review_trip_widths,
            "No trips require review.",
        ),
    )

    audit_rows = [[
        cell(entry.get("created_at")),
        cell(entry.get("action")),
        cell(entry.get("actor_id")),
        cell(str(entry.get("details") or {})),
    ] for entry in report.get("audit_history", [])]
    add_section(
        story,
        "Payroll audit history",
        make_table(
            ["Date", "Action", "User", "Details"],
            audit_rows,
            [available_width * weight / 100 for weight in (21, 20, 21, 38)],
            "No payroll audit history recorded.",
        ),
    )

    for document_index, driver in enumerate(summary_drivers, start=1):
        story.append(PageBreak())
        driver_name = str(driver.get("driver_name") or "Unassigned Driver")
        document_number = f"PAY-{payroll_number}-DOC-{document_index:03d}"
        transaction_id = f"TXN-{payroll_number}-{document_index:03d}"
        story.extend([
            Paragraph("Employee Payslip", title_style),
            Paragraph(f"<b>Employee:</b> {_text(driver_name)}", body_style),
            Paragraph(f"<b>Driver ID:</b> {_text(driver.get('driver_id'))}", body_style),
            Paragraph(
                f"<b>Payroll #{_text(payroll_number)}</b> · {escape(short_period)} · "
                f"<b>Document {document_index} of {document_count}</b>",
                body_style,
            ),
            Paragraph(
                f"<b>Document Number:</b> {_text(document_number)} · "
                f"<b>Transaction ID:</b> {_text(transaction_id)}",
                body_style,
            ),
            Paragraph(escape(period), body_style),
            Paragraph(escape(filter_summary), small_style),
            Spacer(1, 3 * mm),
        ])
        driver_key = driver.get("driver_key") or f"id:{driver.get('driver_id')}"
        driver_trips = [
            trip for trip in trips
            if trip_key(trip) == driver_key
            and (trip.get("eligible") or trip.get("reference_only"))
        ]
        earnings_rows = [[
            cell(trip.get("payroll_date")),
            cell(trip.get("ism_no")),
            cell(trip.get("origin")),
            cell(trip.get("destination")),
            cell(_money(trip.get("rate")), right_style),
            cell(trip.get("issue") or ("Eligible" if trip.get("eligible") else "Needs review")),
        ] for trip in driver_trips]
        earnings_heading = Paragraph(
            (
                f"EMPLOYEE PAYSLIP · {_text(driver_name)} · "
                f"{escape(start_date)} to {escape(end_date)} · "
                f"{escape(str(report.get('status', 'draft')).title())}"
            ),
            header_style,
        )
        earnings_headers = [
            "Date", "ISM Number", "Origin", "Destination", "Trip rate", "Status",
        ]
        earnings_widths = [
            available_width * weight / 100 for weight in (13, 17, 16, 16, 15, 23)
        ]
        story.append(make_table(
            earnings_headers,
            earnings_rows,
            earnings_widths,
            "No trip line items match the selected filters.",
            earnings_heading,
        ))

        remaining_overdraft = (
            driver.get("remaining_overdraft")
            if driver.get("remaining_overdraft") is not None
            else driver.get("overdraft_balance")
        )
        driver_advances = [
            advance for advance in report.get("cash_advances", [])
            if str(advance.get("driver_id")) == str(driver.get("driver_id"))
        ]
        final_net = (
            driver.get("final_net_pay")
            if driver.get("final_net_pay") is not None
            else max(Decimal(str(driver.get("net_before_overdraft") or 0)), Decimal("0"))
        )
        cash_advances = Decimal(str(driver.get("cash_advances") or 0))
        overdraft_values = [
            ("opening_overdraft", "Opening overdraft", driver.get("opening_overdraft")),
            ("new_overdraft", "New overdraft", driver.get("new_overdraft")),
            ("overdraft_deduction", "Overdraft deduction", driver.get("overdraft_deduction")),
            ("remaining_overdraft", "Outstanding overdraft", remaining_overdraft),
        ]
        deduction_rows = []
        if cash_advances:
            deduction_rows.append(["Cash advances", _money(cash_advances)])
        deduction_rows.extend(
            [label, _money(value)]
            for _, label, value in overdraft_values
            if Decimal(str(value or 0))
        )
        has_overdraft = bool(driver.get("overdraft_transactions")) or any(
            Decimal(str(value or 0))
            for key, _, value in overdraft_values
            if key != "remaining_overdraft"
        ) or Decimal(str(remaining_overdraft or 0)) != 0
        summary_widths = (
            [available_width * 0.23, available_width * 0.17]
            if deduction_rows
            else [available_width * 0.65, available_width * 0.35]
        )
        net_rows = [
            ["Gross earnings", _money(driver.get("gross_pay"))],
        ]
        if has_overdraft:
            net_rows.append(["Net before overdraft", _money(driver.get("net_before_overdraft"))])
        net_rows.extend([
            ["Final net pay", _money(final_net)],
            ["Remaining amount due", _money(driver.get("remaining_amount_due"))],
        ])
        net_summary = Table(
            [[Paragraph("<b>NET PAY SUMMARY</b>", body_style)]]
            + [[cell(label), cell(value, right_style)] for label, value in net_rows],
            colWidths=summary_widths,
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), _LIGHT),
                ("BOX", (0, 0), (-1, -1), 0.4, _BORDER),
                ("INNERGRID", (0, 0), (-1, -1), 0.3, _BORDER),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]),
        )
        if deduction_rows:
            deductions_table = Table(
                [[Paragraph("<b>DEDUCTIONS &amp; ADJUSTMENTS</b>", body_style)]]
                + [[cell(label), cell(value, right_style)] for label, value in deduction_rows],
                colWidths=[available_width * 0.23, available_width * 0.17],
                style=TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), _LIGHT),
                    ("BOX", (0, 0), (-1, -1), 0.4, _BORDER),
                    ("INNERGRID", (0, 0), (-1, -1), 0.3, _BORDER),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]),
            )
            financial_summary = Table(
                [[deductions_table, net_summary]],
                colWidths=[available_width / 2, available_width / 2],
                style=TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]),
            )
        else:
            financial_summary = Table(
                [[net_summary]],
                colWidths=[available_width],
                style=TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]),
            )
        story.extend([
            Spacer(1, 3 * mm),
            financial_summary,
            Spacer(1, 3 * mm),
        ])

        if driver_advances:
            add_section(
                story,
                "Cash advance details",
                make_table(
                    ["Date", "Amount", "Reference", "Remarks"],
                    [[
                        cell(advance.get("advance_date")),
                        cell(_money(advance.get("amount")), right_style),
                        cell(advance.get("reference")),
                        cell(advance.get("remarks")),
                    ] for advance in driver_advances],
                    [available_width * weight / 100 for weight in (18, 18, 27, 37)],
                    "No cash advances recorded.",
                ),
            )
        if driver.get("overdraft_transactions"):
            add_section(
                story,
                "Overdraft transaction history",
                make_table(
                    ["Effective date", "Transaction", "Amount", "Remarks"],
                    [[
                        cell(transaction.get("effective_date")),
                        cell(transaction.get("transaction_type")),
                        cell(_money(transaction.get("amount")), right_style),
                        cell(transaction.get("remarks")),
                    ] for transaction in driver.get("overdraft_transactions", [])],
                    [available_width * weight / 100 for weight in (18, 22, 18, 42)],
                    "No overdraft transactions recorded.",
                ),
            )
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(
            "Employee acknowledgement: ____________________________________"
            " &nbsp;&nbsp;&nbsp; Date: ____________________",
            small_style,
        ))
    def draw_page(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        logo_width, logo_height = ImageReader(report_logo_path()).getSize()
        rendered_logo_width = 37 * mm
        canvas.drawImage(
            report_logo_path(),
            12 * mm,
            page_height - 25 * mm,
            width=rendered_logo_width,
            height=rendered_logo_width * logo_height / logo_width,
            preserveAspectRatio=True,
            mask="auto",
        )
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(_SLATE)
        canvas.drawRightString(page_width - 12 * mm, page_height - 15 * mm, REPORT_ADDRESS)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(_SLATE)
        canvas.drawString(12 * mm, 7 * mm, "Fleet Management System - Payroll")
        canvas.drawRightString(page_width - 12 * mm, 7 * mm, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=draw_page, onLaterPages=draw_page)
    output.seek(0)
    return output
