from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from xlsform_lint.diagnostics import (
    Diagnostic,
    DiagnosticOrigin,
    Severity,
    SourceConfidence,
    SourceLocation,
    sort_diagnostics,
    summarize,
)


def location(**changes: object) -> SourceLocation:
    values = {
        "path": "form.xlsx",
        "sheet": "Survey",
        "row": 14,
        "column": "relevant",
        "cell": "D14",
        "confidence": SourceConfidence.EXACT,
    }
    values.update(changes)
    return SourceLocation(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("severity", "rendered"),
    [(Severity.ERROR, "error"), (Severity.WARNING, "warning"), (Severity.INFO, "info")],
)
def test_severity_representation(severity: Severity, rendered: str) -> None:
    assert str(severity) == rendered


def test_diagnostic_contract_origins_help_related_and_immutability() -> None:
    related = location(row=3, column="name", cell="B3")
    diagnostic = Diagnostic(
        "PX999",
        Severity.ERROR,
        "  normalized\n message  ",
        location(),
        DiagnosticOrigin.PYXFORM,
        help="upstream conversion failed",
        related=[related],  # type: ignore[arg-type]
    )
    native = Diagnostic(
        "NATIVE-TEST", Severity.INFO, "native contract", None, DiagnosticOrigin.NATIVE
    )

    assert diagnostic.message == "normalized message"
    assert diagnostic.help == "upstream conversion failed"
    assert diagnostic.related == (related,)
    assert native.related == ()
    assert str(diagnostic.origin) == "pyxform"
    assert str(native.origin) == "native"
    with pytest.raises(FrozenInstanceError):
        diagnostic.message = "changed"  # type: ignore[misc]


def test_source_confidence_preserves_only_declared_precision_and_sheet_casing() -> None:
    exact = location()
    row = SourceLocation("form.xlsx", "Survey", 14, confidence=SourceConfidence.ROW)
    sheet = SourceLocation("form.xlsx", "Survey", confidence=SourceConfidence.SHEET)
    file = SourceLocation("form.xlsx", confidence=SourceConfidence.FILE)

    assert exact.confidence is SourceConfidence.EXACT
    assert exact.sheet == "Survey"
    assert row.column is row.cell is None
    assert sheet.row is sheet.column is sheet.cell is None
    assert file.sheet is file.row is file.column is file.cell is None
    assert [exact.confidence, row.confidence, sheet.confidence, file.confidence] == [
        SourceConfidence.EXACT,
        SourceConfidence.ROW,
        SourceConfidence.SHEET,
        SourceConfidence.FILE,
    ]


@pytest.mark.parametrize(
    "invalid",
    [
        {"path": "form.xlsx", "sheet": "Survey", "confidence": SourceConfidence.FILE},
        {"path": "form.xlsx", "sheet": "Survey", "row": 2, "confidence": SourceConfidence.SHEET},
        {"path": "form.xlsx", "sheet": "Survey", "confidence": SourceConfidence.ROW},
        {"path": "form.xlsx", "sheet": "Survey", "row": 2, "confidence": SourceConfidence.EXACT},
    ],
)
def test_source_helpers_never_upgrade_or_accept_fabricated_precision(
    invalid: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="declared confidence"):
        SourceLocation(**invalid)  # type: ignore[arg-type]


def test_sorting_is_a_total_order_independent_of_construction_order() -> None:
    diagnostics = (
        Diagnostic("R2", Severity.ERROR, "same", location(), DiagnosticOrigin.NATIVE),
        Diagnostic("R1", Severity.ERROR, "same", location(), DiagnosticOrigin.NATIVE),
        Diagnostic("R1", Severity.WARNING, "same", location(), DiagnosticOrigin.NATIVE),
        Diagnostic("R1", Severity.WARNING, "other", location(), DiagnosticOrigin.PYXFORM),
        Diagnostic("R1", Severity.WARNING, "same", location(cell="E14"), DiagnosticOrigin.NATIVE),
        Diagnostic("R1", Severity.WARNING, "same", location(column="type", cell="A14"), DiagnosticOrigin.NATIVE),
        Diagnostic("R1", Severity.WARNING, "same", location(row=4, cell="D4"), DiagnosticOrigin.NATIVE),
        Diagnostic("R1", Severity.WARNING, "same", location(sheet="choices"), DiagnosticOrigin.NATIVE),
        Diagnostic("R1", Severity.WARNING, "same", location(path="z.xlsx"), DiagnosticOrigin.NATIVE),
        Diagnostic("R1", Severity.WARNING, "unsourced", None, DiagnosticOrigin.NATIVE),
    )
    expected = sort_diagnostics(diagnostics)
    permutations = (
        diagnostics,
        tuple(reversed(diagnostics)),
        diagnostics[3:] + diagnostics[:3],
        diagnostics[::2] + diagnostics[1::2],
    )
    assert all(sort_diagnostics(items) == expected for items in permutations)
    assert expected[0].source is None
    assert [item.rule_id for item in expected if item.source == location()] == [
        "R1",
        "R1",
        "R1",
        "R2",
    ]


@pytest.mark.parametrize(
    ("severities", "expected"),
    [
        ((), (0, 0, 0)),
        ((Severity.ERROR,), (1, 0, 0)),
        ((Severity.WARNING,), (0, 1, 0)),
        ((Severity.INFO,), (0, 0, 1)),
        ((Severity.ERROR, Severity.WARNING, Severity.INFO, Severity.ERROR), (2, 1, 1)),
    ],
)
def test_structured_summary_counts(
    severities: tuple[Severity, ...], expected: tuple[int, int, int]
) -> None:
    diagnostics = [
        Diagnostic(f"R{index}", severity, "message", None, DiagnosticOrigin.NATIVE)
        for index, severity in enumerate(severities)
    ]
    summary = summarize(diagnostics)
    assert (summary.errors, summary.warnings, summary.info) == expected
