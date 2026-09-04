"""Minimal read-once Phase 1 lint orchestration."""

from __future__ import annotations

from pathlib import Path
from zipfile import BadZipFile

from openpyxl.utils.exceptions import InvalidFileException

from .diagnostics import Diagnostic, sort_diagnostics
from .pyxform_adapter import validate_workbook
from .source_reader import read_sheet_names
from .workbook_input import read_workbook_bytes


class InputError(Exception):
    """A predictable input acquisition or workbook-format failure."""


def lint_workbook(path: str | Path) -> tuple[Diagnostic, ...]:
    """Acquire the path once, then feed independent in-memory lane copies."""

    input_path = Path(path)
    if not input_path.exists():
        raise InputError(f"input does not exist: {input_path}")
    if not input_path.is_file():
        raise InputError(f"input is not a file: {input_path}")
    if input_path.suffix.casefold() != ".xlsx":
        raise InputError(f"input is not an .xlsx workbook: {input_path}")

    try:
        workbook_bytes = read_workbook_bytes(input_path)
        read_sheet_names(workbook_bytes)
    except (OSError, BadZipFile, InvalidFileException, KeyError, ValueError) as error:
        raise InputError(f"unable to read XLSX input: {input_path}") from error

    diagnostic = validate_workbook(workbook_bytes, str(input_path))
    return sort_diagnostics(()) if diagnostic is None else sort_diagnostics((diagnostic,))
