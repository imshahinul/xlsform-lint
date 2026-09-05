"""Deterministic implementations of exactly seven frozen Phase 3 rules."""

from __future__ import annotations

import re
from typing import Any

from openpyxl.utils import get_column_letter

from .diagnostics import (
    Diagnostic,
    DiagnosticOrigin,
    Severity,
    SourceConfidence,
    SourceLocation,
)
from .native_model import (
    ChoiceRow,
    HeaderCell,
    SelectKind,
    SheetFacts,
    SurveyRow,
    SurveyTypeCategory,
    WorkbookFacts,
    is_blank,
    row_value,
    semantic_text,
)


_REFERENCE = re.compile(r"\$\{(?P<name>[^{}]+)\}")
_LABEL_BEARING = {SurveyTypeCategory.VISIBLE, SurveyTypeCategory.NOTE}


def _location(path: str, sheet: SheetFacts, row: int, header: HeaderCell) -> SourceLocation:
    return SourceLocation(
        path=path,
        sheet=sheet.physical_name,
        row=row,
        column=header.actual,
        cell=f"{get_column_letter(header.index + 1)}{row}",
        confidence=SourceConfidence.EXACT,
    )


def _diagnostic(
    rule_id: str,
    severity: Severity,
    message: str,
    path: str,
    sheet: SheetFacts,
    row: int,
    header: HeaderCell,
    *,
    related: tuple[SourceLocation, ...] = (),
) -> Diagnostic:
    return Diagnostic(
        rule_id, severity, message, _location(path, sheet, row, header),
        DiagnosticOrigin.NATIVE, related=related,
    )


def _label_state(row: SurveyRow | ChoiceRow) -> tuple[str, tuple[tuple[Any, HeaderCell, str], ...]] | None:
    """Return plain or translated label context; translated columns take precedence."""

    sheet = row.sheet
    translations = tuple(
        (row.values[column.index] if column.index < len(row.values) else None,
         next(header for header in sheet.headers if header.index == column.index),
         column.language)
        for column in sheet.translations
        if column.actual.strip().casefold() not in sheet.ambiguous_headers
    )
    if translations:
        return "translated", translations
    header = sheet.unique_headers.get("label")
    if header is None:
        return None
    value = row.values[header.index] if header.index < len(row.values) else None
    return "plain", ((value, header, ""),)


def run_cho001(model: WorkbookFacts, path: str) -> tuple[Diagnostic, ...]:
    sheet = model.choices_sheet
    if sheet is None or "list_name" not in sheet.unique_headers:
        return ()
    # Any select-like syntax we cannot map confidently could use a workbook list.
    if any(usage.kind is not SelectKind.INTERNAL_STATIC for usage in model.select_usage):
        return ()
    used = {usage.list_name for usage in model.select_usage if usage.list_name is not None}
    # An unresolved static list makes the choices relationship semantically unsafe;
    # pyxform owns that validity failure, so CHO001 does not add collateral noise.
    if not used.issubset(model.choice_rows_by_list):
        return ()
    header = sheet.unique_headers["list_name"]
    findings = []
    for list_name, rows in model.choice_rows_by_list.items():
        if list_name not in used:
            findings.append(_diagnostic(
                "CHO001", Severity.WARNING,
                f"unused-choice-list: list '{list_name}' is defined but is not referenced by an internal select.",
                path, sheet, rows[0].row, header,
            ))
    return tuple(findings)


def run_lbl001(model: WorkbookFacts, path: str) -> tuple[Diagnostic, ...]:
    findings = []
    for row in model.survey_rows:
        if row.category not in _LABEL_BEARING:
            continue
        state = _label_state(row)
        if state is None:
            continue
        _, labels = state
        if all(is_blank(value) for value, _, _ in labels):
            name = semantic_text(row_value(row, "name")) or "<unnamed>"
            findings.append(_diagnostic(
                "LBL001", Severity.WARNING,
                f"missing-visible-question-label: visible question '{name}' has no label.",
                path, row.sheet, row.row, labels[0][1],
            ))
    return tuple(findings)


def run_lbl002(model: WorkbookFacts, path: str) -> tuple[Diagnostic, ...]:
    findings = []
    for row in model.choice_rows:
        name = semantic_text(row_value(row, "name"))
        if name is None:
            continue
        state = _label_state(row)
        if state is None:
            continue
        _, labels = state
        if all(is_blank(value) for value, _, _ in labels):
            list_name = semantic_text(row_value(row, "list_name")) or "<unknown>"
            findings.append(_diagnostic(
                "LBL002", Severity.WARNING,
                f"blank-choice-label: choice '{name}' in list '{list_name}' has no label.",
                path, row.sheet, row.row, labels[0][1],
            ))
    return tuple(findings)


def _i18n_rows(rows: tuple[SurveyRow | ChoiceRow, ...], path: str) -> tuple[Diagnostic, ...]:
    findings = []
    for row in rows:
        if isinstance(row, SurveyRow) and row.category not in _LABEL_BEARING:
            continue
        if isinstance(row, ChoiceRow) and semantic_text(row_value(row, "name")) is None:
            continue
        state = _label_state(row)
        if state is None or state[0] != "translated" or len(state[1]) < 2:
            continue
        labels = state[1]
        populated = [(value, header, language) for value, header, language in labels if not is_blank(value)]
        if not populated:
            continue
        populated_language = populated[0][2]
        for value, header, language in labels:
            if is_blank(value):
                findings.append(_diagnostic(
                    "I18N001", Severity.WARNING,
                    f"incomplete-translation: label::{language} is missing while label::{populated_language} is populated.",
                    path, row.sheet, row.row, header,
                ))
    return tuple(findings)


def run_i18n001(model: WorkbookFacts, path: str) -> tuple[Diagnostic, ...]:
    return _i18n_rows(model.survey_rows, path) + _i18n_rows(model.choice_rows, path)


def run_ux001(model: WorkbookFacts, path: str) -> tuple[Diagnostic, ...]:
    sheet = model.survey_sheet
    if sheet is None or "constraint" not in sheet.unique_headers:
        return ()
    message_headers = tuple(
        header for header in sheet.headers
        if header.logical == "constraint_message" or header.logical.startswith("constraint_message::")
    )
    if len({header.logical for header in message_headers}) != len(message_headers):
        return ()
    constraint_header = sheet.unique_headers["constraint"]
    findings = []
    for row in model.survey_rows:
        if is_blank(row_value(row, "constraint")):
            continue
        has_message = any(
            header.index < len(row.values) and not is_blank(row.values[header.index])
            for header in message_headers
        )
        if not has_message:
            findings.append(_diagnostic(
                "UX001", Severity.WARNING,
                "constraint-without-message: constraint is set but constraint_message is empty.",
                path, sheet, row.row, constraint_header,
            ))
    return tuple(findings)


def run_ord001(model: WorkbookFacts, path: str) -> tuple[Diagnostic, ...]:
    sheet = model.survey_sheet
    if sheet is None or "choice_filter" not in sheet.unique_headers:
        return ()
    # Scope reconstruction is explicitly out of scope; structural containers
    # suppress this narrow lexical-order check rather than inviting guesses.
    if any(row.category is SurveyTypeCategory.GROUP_REPEAT for row in model.survey_rows):
        return ()
    header = sheet.unique_headers["choice_filter"]
    findings = []
    for row in model.survey_rows:
        expression = semantic_text(row_value(row, "choice_filter"))
        if expression is None:
            continue
        references = sorted(set(match["name"] for match in _REFERENCE.finditer(expression)))
        for name in references:
            definitions = model.survey_by_name.get(name, ())
            if len(definitions) != 1 or definitions[0].row <= row.row:
                continue
            definition = definitions[0]
            name_header = definition.sheet.unique_headers.get("name")
            related = ((_location(path, definition.sheet, definition.row, name_header),) if name_header else ())
            findings.append(_diagnostic(
                "ORD001", Severity.WARNING,
                f"later-choice-filter-dependency: depends on '${{{name}}}', defined later at survey row {definition.row}. The filter may evaluate before that value is populated.",
                path, sheet, row.row, header, related=related,
            ))
    return tuple(findings)


def run_ux002(model: WorkbookFacts, path: str) -> tuple[Diagnostic, ...]:
    sheet = model.survey_sheet
    if sheet is None or "required" not in sheet.unique_headers or "default" not in sheet.unique_headers:
        return ()
    required_header = sheet.unique_headers["required"]
    findings = []
    for row in model.survey_rows:
        required = semantic_text(row_value(row, "required"))
        if required is not None and required.casefold() == "yes" and not is_blank(row_value(row, "default")):
            findings.append(_diagnostic(
                "UX002", Severity.INFO,
                "required-with-default: required question also has a default value; confirm that the default is intentional.",
                path, sheet, row.row, required_header,
            ))
    return tuple(findings)


NATIVE_RULES = (
    run_cho001, run_lbl001, run_lbl002, run_i18n001,
    run_ux001, run_ord001, run_ux002,
)


def run_native_rules(model: WorkbookFacts, path: str) -> tuple[Diagnostic, ...]:
    return tuple(finding for rule in NATIVE_RULES for finding in rule(model, path))
