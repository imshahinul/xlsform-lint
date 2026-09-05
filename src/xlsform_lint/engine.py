"""Read-once orchestration for independent native and pyxform lanes."""

from __future__ import annotations

from pathlib import Path
from zipfile import BadZipFile

from openpyxl.utils.exceptions import InvalidFileException

from .diagnostics import Diagnostic, sort_diagnostics
from .native_model import build_native_model
from .native_rules import run_native_rules
from .pyxform_adapter import validate_workbook
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
        native_model = build_native_model(workbook_bytes)
    except (OSError, BadZipFile, InvalidFileException, KeyError, ValueError) as error:
        raise InputError(f"unable to read XLSX input: {input_path}") from error

    native_diagnostics = run_native_rules(native_model, str(input_path))
    pyxform_diagnostic = validate_workbook(workbook_bytes, str(input_path))
    combined = native_diagnostics + (() if pyxform_diagnostic is None else (pyxform_diagnostic,))
    return sort_diagnostics(combined)
