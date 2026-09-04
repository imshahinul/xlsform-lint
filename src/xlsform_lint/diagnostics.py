"""Immutable diagnostic contract and deterministic kernel operations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum
from os.path import normcase, normpath
from typing import Iterable


class Severity(IntEnum):
    """Stable severities ordered for fail-threshold comparisons."""

    INFO = 0
    WARNING = 1
    ERROR = 2

    def __str__(self) -> str:
        return self.name.lower()


class DiagnosticOrigin(str, Enum):
    """The semantic owner of a diagnostic."""

    PYXFORM = "pyxform"
    NATIVE = "native"

    def __str__(self) -> str:
        return self.value


class SourceConfidence(str, Enum):
    """The precision deterministically known for a source location."""

    EXACT = "exact"
    ROW = "row"
    SHEET = "sheet"
    FILE = "file"


@dataclass(frozen=True)
class SourceLocation:
    """A real workbook location, with no inferred placeholder precision."""

    path: str
    sheet: str | None = None
    row: int | None = None
    column: str | None = None
    cell: str | None = None
    confidence: SourceConfidence = SourceConfidence.FILE

    def __post_init__(self) -> None:
        if not self.path:
            raise ValueError("source path must not be empty")
        if self.row is not None and self.row < 1:
            raise ValueError("source row must be a positive physical row")

        if self.confidence is SourceConfidence.FILE:
            valid = self.sheet is self.row is self.column is self.cell is None
        elif self.confidence is SourceConfidence.SHEET:
            valid = self.sheet is not None and all(
                value is None for value in (self.row, self.column, self.cell)
            )
        elif self.confidence is SourceConfidence.ROW:
            valid = (
                self.sheet is not None
                and self.row is not None
                and self.column is None
                and self.cell is None
            )
        else:
            valid = (
                self.sheet is not None
                and self.row is not None
                and (self.column is not None or self.cell is not None)
            )
        if not valid:
            raise ValueError("source fields do not match declared confidence")


@dataclass(frozen=True)
class Diagnostic:
    """A formatter-independent lint finding."""

    rule_id: str
    severity: Severity
    message: str
    source: SourceLocation | None
    origin: DiagnosticOrigin
    help: str | None = None
    related: tuple[SourceLocation, ...] = ()

    def __post_init__(self) -> None:
        if not self.rule_id:
            raise ValueError("rule ID must not be empty")
        normalized_message = " ".join(self.message.split())
        if not normalized_message:
            raise ValueError("diagnostic message must not be empty")
        object.__setattr__(self, "message", normalized_message)
        object.__setattr__(self, "related", tuple(self.related))


@dataclass(frozen=True)
class DiagnosticSummary:
    """Structured counts derived directly from diagnostics."""

    errors: int = 0
    warnings: int = 0
    info: int = 0


def diagnostic_sort_key(diagnostic: Diagnostic) -> tuple[object, ...]:
    """Return the total order: path, source rank, sheet order/name, row,
    logical column, cell, rule, severity, origin, message, help, and related.
    """

    source = diagnostic.source
    if source is None:
        location: tuple[object, ...] = ("", 0, 4, "", -1, "", "")
    else:
        sheet = source.sheet or ""
        canonical_sheet_order = {"survey": 0, "choices": 1, "settings": 2}
        location = (
            normcase(normpath(source.path)),
            1,
            canonical_sheet_order.get(sheet.casefold(), 3),
            sheet.casefold(),
            source.row if source.row is not None else -1,
            source.column or "",
            source.cell or "",
        )
    related = tuple(
        (
            normcase(normpath(item.path)),
            item.sheet or "",
            item.row if item.row is not None else -1,
            item.column or "",
            item.cell or "",
            item.confidence.value,
        )
        for item in diagnostic.related
    )
    return location + (
        diagnostic.rule_id,
        int(diagnostic.severity),
        diagnostic.origin.value,
        diagnostic.message,
        diagnostic.help or "",
        related,
    )


def sort_diagnostics(diagnostics: Iterable[Diagnostic]) -> tuple[Diagnostic, ...]:
    """Sort diagnostics independently of their construction order."""

    return tuple(sorted(diagnostics, key=diagnostic_sort_key))


def summarize(diagnostics: Iterable[Diagnostic]) -> DiagnosticSummary:
    """Count each severity without parsing rendered output."""

    counts = {severity: 0 for severity in Severity}
    for diagnostic in diagnostics:
        counts[diagnostic.severity] += 1
    return DiagnosticSummary(
        errors=counts[Severity.ERROR],
        warnings=counts[Severity.WARNING],
        info=counts[Severity.INFO],
    )


def exit_code_for(
    diagnostics: Iterable[Diagnostic], threshold: Severity = Severity.ERROR
) -> int:
    """Return 1 when a finding meets the threshold, otherwise return 0."""

    return int(any(item.severity >= threshold for item in diagnostics))
