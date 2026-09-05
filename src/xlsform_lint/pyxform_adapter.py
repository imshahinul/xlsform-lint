"""Supported pyxform boundary and pyxform 4.5 failure normalization."""

from __future__ import annotations

from difflib import SequenceMatcher
from io import BytesIO
import re

from pyxform import errors
from pyxform.xls2xform import ConvertResult, convert

from .diagnostics import (
    Diagnostic,
    DiagnosticOrigin,
    Severity,
    SourceConfidence,
    SourceLocation,
)
from .source_reader import SourceCell, WorkbookSourceIndex, read_source_index


_ROW_PREFIX = r"\[row : (?P<row>\d+)\]"
_PX001 = re.compile(
    _ROW_PREFIX
    + r" On the 'survey' sheet, the 'name' value '(?P<token>[^']+)' is invalid\. "
    r"Questions, groups, and repeats must be unique within their nearest parent "
    r"group or repeat, or the survey if not inside a group or repeat\."
)
_PX002 = re.compile(
    _ROW_PREFIX
    + r" On the 'survey' sheet, the 'name' value is invalid\. Names must begin "
    r"with a letter or underscore\. After the first character, names may contain "
    r"letters, digits, underscores, hyphens, or periods\."
)
_PX003_NO_NAME = re.compile(_ROW_PREFIX + r" Question or group with no name\.")
_PX003_NO_TYPE = re.compile(_ROW_PREFIX + r" Question with no type\.\n.*", re.DOTALL)
_PX004 = re.compile(_ROW_PREFIX + r" List name not in choices sheet: (?P<token>\S+)")
_PX005 = re.compile(
    _ROW_PREFIX
    + r" On the 'survey' sheet, the '(?P<column>[^']+)' value is invalid\. "
    r"Reference variables must contain a name from the 'survey' sheet\. "
    r"Could not find the name '(?P<token>[^']+)'\."
)
_PX006 = re.compile(
    _ROW_PREFIX
    + r" On the 'choices' sheet, the 'name' value is invalid\. Choice names must "
    r"be unique for each choice list\. If this is intentional, use the setting "
    r"'allow_choice_duplicates'\. Learn more: https://xlsform\.org/#choice-names\."
)


def convert_workbook(workbook_bytes: bytes) -> ConvertResult:
    """Convert an independent stream copy without external validation."""

    return convert(BytesIO(workbook_bytes), validate=False)


def _safe_upstream_message(error: errors.PyXFormError) -> str:
    message = " ".join(str(error).split())
    return message or "pyxform conversion failed."


def suggest_field_name(
    missing: str, candidates: tuple[str, ...], *, threshold: float = 0.78
) -> str | None:
    """Return one strong, unique typo suggestion, independent of input ordering.

    SequenceMatcher ratio 0.78 is intentionally conservative. Equal best scores
    are ambiguous and suppressed; only names other than the missing token qualify.
    """

    scored = sorted(
        {
            (SequenceMatcher(None, missing, candidate).ratio(), candidate)
            for candidate in candidates
            if candidate and candidate != missing
        },
        reverse=True,
    )
    if not scored or scored[0][0] < threshold:
        return None
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None
    return scored[0][1]


def _location(path: str, cell: SourceCell | None) -> SourceLocation:
    if cell is None:
        return SourceLocation(path=path, confidence=SourceConfidence.FILE)
    return SourceLocation(
        path=path,
        sheet=cell.sheet,
        row=cell.row,
        column=cell.column,
        cell=cell.cell,
        confidence=SourceConfidence.EXACT,
    )


def _single_cell(
    index: WorkbookSourceIndex, *, sheet: str, row: int, column: str
) -> SourceCell | None:
    matches = index.find(sheet=sheet, row=row, column=column)
    return matches[0] if len(matches) == 1 else None


def _field_names(index: WorkbookSourceIndex) -> tuple[str, ...]:
    return tuple(
        cell.value
        for cell in index.find(sheet="survey", column="name")
        if isinstance(cell.value, str) and cell.value
    )


def _normalize_45(
    error: errors.PyXFormError,
    source_path: str,
    index: WorkbookSourceIndex,
) -> Diagnostic | None:
    """Match only exact, reconnaissance-backed pyxform 4.5 public messages."""

    raw = str(error)
    match = _PX001.fullmatch(raw)
    if match:
        row, token = int(match["row"]), match["token"]
        cell = _single_cell(index, sheet="survey", row=row, column="name")
        prior = tuple(
            item
            for item in index.find(sheet="survey", column="name")
            if item.row < row and item.value == token
        )
        # Pyxform owns scope validity. A related location is safe only when there
        # is exactly one lexical predecessor; no scope validator is recreated.
        related = (_location(source_path, prior[0]),) if len(prior) == 1 else ()
        return Diagnostic(
            "PX001",
            Severity.ERROR,
            f"duplicate-name-in-scope: '{token}' duplicates another name in the same XLSForm scope.",
            _location(source_path, cell),
            DiagnosticOrigin.PYXFORM,
            related=related,
        )

    match = _PX002.fullmatch(raw)
    if match:
        row = int(match["row"])
        cell = _single_cell(index, sheet="survey", row=row, column="name")
        token = cell.value if cell is not None and isinstance(cell.value, str) else None
        message = "invalid-survey-name: invalid XLSForm field name."
        if token is not None:
            message = f"invalid-survey-name: '{token}' is not a valid XLSForm field name."
        return Diagnostic(
            "PX002",
            Severity.ERROR,
            message,
            _location(source_path, cell),
            DiagnosticOrigin.PYXFORM,
        )

    match = _PX003_NO_NAME.fullmatch(raw)
    if match:
        row, column = int(match["row"]), "name"
    else:
        match = _PX003_NO_TYPE.fullmatch(raw)
        if not match:
            row = 0
            column = ""
        else:
            row, column = int(match["row"]), "type"
    if match:
        candidates = index.find(sheet="survey", row=row)
        physical_sheet = candidates[0].sheet if candidates else None
        source = (
            SourceLocation(
                source_path,
                sheet=physical_sheet,
                row=row,
                confidence=SourceConfidence.ROW,
            )
            if physical_sheet
            else SourceLocation(source_path, confidence=SourceConfidence.FILE)
        )
        return Diagnostic(
            "PX003",
            Severity.ERROR,
            f"missing-required-structural-value: required '{column}' value is missing.",
            source,
            DiagnosticOrigin.PYXFORM,
        )

    match = _PX004.fullmatch(raw)
    if match:
        row, token = int(match["row"]), match["token"]
        cell = _single_cell(index, sheet="survey", row=row, column="type")
        return Diagnostic(
            "PX004",
            Severity.ERROR,
            f"unknown-internal-choice-list: internal choice list '{token}' does not exist.",
            _location(source_path, cell),
            DiagnosticOrigin.PYXFORM,
        )

    match = _PX005.fullmatch(raw)
    if match:
        row, column, token = int(match["row"]), match["column"], match["token"]
        candidates = tuple(
            cell
            for cell in index.find(sheet="survey", row=row, column=column)
            if isinstance(cell.value, str) and f"${{{token}}}" in cell.value
        )
        suggestion = suggest_field_name(token, _field_names(index))
        message = f"unknown-field-reference: '{token}' does not exist."
        if suggestion:
            message += f" Did you mean '{suggestion}'?"
        return Diagnostic(
            "PX005",
            Severity.ERROR,
            message,
            _location(source_path, candidates[0] if len(candidates) == 1 else None),
            DiagnosticOrigin.PYXFORM,
        )

    match = _PX006.fullmatch(raw)
    if match:
        row = int(match["row"])
        cell = _single_cell(index, sheet="choices", row=row, column="name")
        token = cell.value if cell is not None and isinstance(cell.value, str) else None
        message = "duplicate-choice-value: duplicate choice name in a choice list."
        if token is not None:
            message = f"duplicate-choice-value: '{token}' duplicates another choice name in its list."
        related: tuple[SourceLocation, ...] = ()
        if cell is not None and token is not None:
            list_cell = _single_cell(index, sheet="choices", row=row, column="list_name")
            if list_cell is not None:
                prior = tuple(
                    item
                    for item in index.find(sheet="choices", column="name")
                    if item.row < row
                    and item.value == token
                    and (prior_list := _single_cell(index, sheet="choices", row=item.row, column="list_name"))
                    and prior_list.value == list_cell.value
                )
                if len(prior) == 1:
                    related = (_location(source_path, prior[0]),)
        return Diagnostic(
            "PX006",
            Severity.ERROR,
            message,
            _location(source_path, cell),
            DiagnosticOrigin.PYXFORM,
            related=related,
        )
    return None


def validate_workbook(workbook_bytes: bytes, source_path: str) -> Diagnostic | None:
    """Convert once and normalize the first fatal supported pyxform failure."""

    try:
        convert_workbook(workbook_bytes)
    except errors.PyXFormError as error:
        index = read_source_index(workbook_bytes)
        recognized = _normalize_45(error, source_path, index)
        if recognized is not None:
            return recognized
        return Diagnostic(
            rule_id="PX999",
            severity=Severity.ERROR,
            message=f"pyxform-error: {_safe_upstream_message(error)}",
            source=SourceLocation(path=source_path, confidence=SourceConfidence.FILE),
            origin=DiagnosticOrigin.PYXFORM,
        )
    return None
