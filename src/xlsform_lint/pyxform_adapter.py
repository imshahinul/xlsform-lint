"""Supported pyxform conversion boundary for immutable workbook bytes."""

from io import BytesIO

from pyxform.xls2xform import ConvertResult, convert


def convert_workbook(workbook_bytes: bytes) -> ConvertResult:
    """Convert an independent stream copy without external validation."""

    return convert(BytesIO(workbook_bytes), validate=False)
