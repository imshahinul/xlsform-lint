from __future__ import annotations

import pytest

from xlsform_lint.diagnostics import (
    Diagnostic,
    DiagnosticOrigin,
    Severity,
    SourceConfidence,
    SourceLocation,
)
from xlsform_lint.text_formatter import format_diagnostics, render_source


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (SourceLocation("form.xlsx"), "form.xlsx"),
        (SourceLocation("form.xlsx", "Survey", confidence=SourceConfidence.SHEET), "form.xlsx:Survey"),
        (SourceLocation("form.xlsx", "Survey", 14, confidence=SourceConfidence.ROW), "form.xlsx:Survey:14"),
        (SourceLocation("form.xlsx", "Survey", 14, "relevant", "D14", SourceConfidence.EXACT), "form.xlsx:Survey:14:relevant"),
        (SourceLocation("form.xlsx", "Survey", 14, cell="D14", confidence=SourceConfidence.EXACT), "form.xlsx:Survey:14:D14"),
    ],
)
def test_source_rendering(source: SourceLocation, expected: str) -> None:
    assert render_source(source) == expected


def test_exact_px999_rendering_and_singular_summary() -> None:
    diagnostic = Diagnostic(
        "PX999",
        Severity.ERROR,
        "pyxform-error: Unknown question type 'definitely_not_a_type'.",
        SourceLocation("fatal.xlsx"),
        DiagnosticOrigin.PYXFORM,
    )
    assert format_diagnostics([diagnostic]) == (
        "fatal.xlsx\n"
        "PX999 error pyxform-error: Unknown question type 'definitely_not_a_type'.\n\n"
        "1 error, 0 warnings\n"
    )


def test_formatter_orders_multiple_diagnostics_and_handles_unsourced() -> None:
    diagnostics = [
        Diagnostic("R2", Severity.WARNING, "second", None, DiagnosticOrigin.NATIVE),
        Diagnostic("R1", Severity.WARNING, "first", SourceLocation("a.xlsx"), DiagnosticOrigin.NATIVE),
    ]
    assert format_diagnostics(diagnostics) == (
        "R2 warning second\n\n"
        "a.xlsx\nR1 warning first\n\n"
        "0 errors, 2 warnings\n"
    )


def test_zero_and_plural_summary_and_safe_plain_text() -> None:
    output = format_diagnostics([])
    assert output == "0 errors, 0 warnings\n"
    forbidden = ("object at 0x", "Traceback", "/var/folders/", "\x1b[")
    assert all(value not in output for value in forbidden)
