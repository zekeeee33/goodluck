from __future__ import annotations

from copy import copy
import os

from openpyxl import Workbook
from openpyxl.drawing.image import Image as ExcelImage
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

REPORT_LOGO_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "static",
    "report-logo.png",
)
REPORT_ADDRESS = (
    "Dragon Commercial Complex, National Highway, "
    "City of Tacurong, 9800 Sultan Kudarat"
)


def add_excel_report_branding(workbook: Workbook) -> None:
    for worksheet in workbook.worksheets:
        title_cell = worksheet["A1"]
        title = title_cell.value
        title_style = copy(title_cell._style)
        row_one_merges = [
            merged_range
            for merged_range in worksheet.merged_cells.ranges
            if merged_range.min_row == 1 and merged_range.min_col == 1
        ]
        for merged_range in row_one_merges:
            worksheet.unmerge_cells(str(merged_range))

        last_column = max(worksheet.max_column, 6)
        worksheet.column_dimensions["A"].width = max(
            worksheet.column_dimensions["A"].width or 0, 16
        )
        worksheet.merge_cells(
            start_row=1,
            start_column=2,
            end_row=1,
            end_column=last_column,
        )
        title_cell.value = None
        branded_title = worksheet.cell(row=1, column=2, value=title)
        if title_style is not None:
            branded_title._style = title_style
        worksheet.row_dimensions[1].height = max(
            worksheet.row_dimensions[1].height or 0, 72
        )

        row_two_merges = [
            merged_range
            for merged_range in worksheet.merged_cells.ranges
            if merged_range.min_row <= 2 <= merged_range.max_row
            and merged_range.min_col <= 2 <= merged_range.max_col
        ]
        for merged_range in row_two_merges:
            worksheet.unmerge_cells(str(merged_range))
        worksheet.merge_cells(
            start_row=2,
            start_column=2,
            end_row=2,
            end_column=last_column,
        )
        address_cell = worksheet.cell(row=2, column=2, value=REPORT_ADDRESS)
        address_cell.font = Font(name="Aptos", size=11, color="475569")
        address_cell.alignment = Alignment(
            horizontal="left",
            vertical="center",
            wrap_text=True,
        )
        worksheet.row_dimensions[2].height = max(
            worksheet.row_dimensions[2].height or 0, 24
        )

        logo = ExcelImage(REPORT_LOGO_PATH)
        logo_aspect_ratio = logo.width / logo.height
        logo.width = 96
        logo.height = logo.width / logo_aspect_ratio
        worksheet.add_image(logo, "A1")

        worksheet.print_area = (
            f"A1:{get_column_letter(last_column)}{worksheet.max_row}"
        )


def report_logo_path() -> str:
    return REPORT_LOGO_PATH
