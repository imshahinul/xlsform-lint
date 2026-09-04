"""Minimal source-fidelity access to workbook bytes."""

from io import BytesIO
from typing import Any

from openpyxl import load_workbook


def read_source_cell(
    workbook_bytes: bytes, sheet_name: str, row: int, column: int
) -> Any:
    """Read one physical cell from an independent in-memory workbook copy."""

    workbook = load_workbook(BytesIO(workbook_bytes), read_only=True, data_only=False)
    try:
        return workbook[sheet_name].cell(row=row, column=column).value
    finally:
        workbook.close()


def read_sheet_names(workbook_bytes: bytes) -> tuple[str, ...]:
    """Return physical sheet names from an independent in-memory copy."""

    workbook = load_workbook(BytesIO(workbook_bytes), read_only=True, data_only=False)
    try:
        return tuple(workbook.sheetnames)
    finally:
        workbook.close()
