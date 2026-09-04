"""Acquire immutable XLSX input for the source and semantic lanes."""

from pathlib import Path


def read_workbook_bytes(path: str | Path) -> bytes:
    """Read the original workbook path at the single input boundary."""

    with Path(path).open("rb") as workbook_file:
        return workbook_file.read()
