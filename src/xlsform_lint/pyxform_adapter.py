"""Supported pyxform conversion boundary for immutable workbook bytes."""

from io import BytesIO

from pyxform import errors
from pyxform.xls2xform import ConvertResult, convert

from .diagnostics import (
    Diagnostic,
    DiagnosticOrigin,
    Severity,
    SourceConfidence,
    SourceLocation,
)


def convert_workbook(workbook_bytes: bytes) -> ConvertResult:
    """Convert an independent stream copy without external validation."""

    return convert(BytesIO(workbook_bytes), validate=False)


def _safe_upstream_message(error: errors.PyXFormError) -> str:
    """Normalize human-facing exception text without using exception repr."""

    message = " ".join(str(error).split())
    return message or "pyxform conversion failed."


def validate_workbook(workbook_bytes: bytes, source_path: str) -> Diagnostic | None:
    """Convert once and normalize the first fatal supported pyxform failure."""

    try:
        convert_workbook(workbook_bytes)
    except errors.PyXFormError as error:
        return Diagnostic(
            rule_id="PX999",
            severity=Severity.ERROR,
            message=f"pyxform-error: {_safe_upstream_message(error)}",
            source=SourceLocation(
                path=source_path,
                confidence=SourceConfidence.FILE,
            ),
            origin=DiagnosticOrigin.PYXFORM,
        )
    return None
