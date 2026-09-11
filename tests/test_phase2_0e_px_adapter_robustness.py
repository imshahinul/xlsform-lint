from __future__ import annotations

from pathlib import Path

import pytest
from pyxform import errors

from xlsform_lint import pyxform_adapter as adapter
from xlsform_lint.diagnostics import DiagnosticOrigin, Severity, SourceConfidence
from xlsform_lint.engine import lint_workbook


SURVEY_HEADER = (
    "type",
    "name",
    "label",
    "relevant",
    "constraint",
    "calculation",
    "choice_filter",
    "default",
)
CHOICES_HEADER = ("list_name", "name", "label")


def _bytes(path: Path) -> bytes:
    return path.read_bytes()


def _boundary_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
    path: Path,
    error: Exception,
):
    calls = 0

    def fail_once(workbook_bytes: bytes):
        nonlocal calls
        calls += 1
        raise error

    monkeypatch.setattr(adapter, "convert_workbook", fail_once)
    diagnostic = adapter.validate_workbook(_bytes(path), str(path))
    assert calls == 1
    assert diagnostic is not None
    assert diagnostic.severity is Severity.ERROR
    assert diagnostic.origin is DiagnosticOrigin.PYXFORM
    return diagnostic


@pytest.mark.parametrize(
    ("message", "rule_id", "confidence", "cell"),
    [
        (
            "  [row : 3]  On the 'survey' sheet, the 'name' value 'dup' is invalid.\n"
            "Questions, groups, and repeats must be unique within their nearest parent "
            "group or repeat, or the survey if not inside a group or repeat.  ",
            "PX001",
            SourceConfidence.EXACT,
            "B3",
        ),
        (
            "[row : 2] On the 'survey' sheet, the 'name' value is invalid. Names must "
            "begin with a letter or underscore. After the first character, names may "
            "contain letters, digits, underscores, hyphens, or periods!",
            "PX002",
            SourceConfidence.EXACT,
            "B2",
        ),
        (
            "[row : 2]\nQuestion or group with no name.",
            "PX003",
            SourceConfidence.ROW,
            None,
        ),
        (
            "[row : 2] List name not in choices sheet: 'missing-list'.",
            "PX004",
            SourceConfidence.EXACT,
            "A2",
        ),
        (
            "[row : 3] On the 'survey' sheet, the 'constraint' value is invalid. "
            "Reference variables must contain a name from the 'survey' sheet. "
            "Could not find the name \"age_yrs\"!",
            "PX005",
            SourceConfidence.EXACT,
            "E3",
        ),
        (
            "[row : 3] On the 'choices' sheet, the 'name' value is invalid. Choice "
            "names must be unique for each choice list. If this is intentional, use "
            "the setting 'allow_choice_duplicates'. Learn more: "
            "https://xlsform.org/#choice-names!",
            "PX006",
            SourceConfidence.EXACT,
            "B3",
        ),
    ],
)
def test_recognized_messages_tolerate_harmless_shape_variation(
    monkeypatch,
    tmp_path,
    xlsform_factory,
    message,
    rule_id,
    confidence,
    cell,
):
    path = xlsform_factory(
        tmp_path / f"{rule_id}.xlsx",
        [
            SURVEY_HEADER,
            ("integer", "age_years" if rule_id == "PX005" else "dup", "First"),
            (
                "select_one missing-list" if rule_id == "PX004" else "text",
                "dup" if rule_id == "PX001" else "question",
                "Second",
                "",
                "${age_yrs} > 17" if rule_id == "PX005" else "",
            ),
        ],
        choices_rows=[
            CHOICES_HEADER,
            ("list", "same", "One"),
            ("list", "same", "Two"),
        ],
    )
    diagnostic = _boundary_diagnostic(
        monkeypatch, path, errors.PyXFormError(message)
    )
    assert diagnostic.rule_id == rule_id
    assert diagnostic.source.confidence is confidence
    assert diagnostic.source.cell == cell


@pytest.mark.parametrize(
    "message",
    [
        "unknown exception message",
        "duplicate name happened somewhere",
        "workbook.xlsx: an unrelated error, with extra context!",
        "[row : 9] Something entirely new happened. See upstream notes.",
        "   \n\t   ",
    ],
)
def test_unknown_pyxform_shapes_are_stable_file_level_px999(
    monkeypatch, tmp_path, workbook_factory, message
):
    path = workbook_factory(tmp_path / "unknown.xlsx")
    diagnostic = _boundary_diagnostic(
        monkeypatch, path, errors.PyXFormError(message)
    )
    assert diagnostic.rule_id == "PX999"
    assert diagnostic.source.path == str(path)
    assert diagnostic.source.sheet is None
    assert diagnostic.source.row is None
    assert diagnostic.source.cell is None
    assert diagnostic.source.confidence is SourceConfidence.FILE


@pytest.mark.parametrize(
    "message",
    [
        "[row : 2] List name not in choices sheet for external select: remote.csv",
        "[row : 2] Dynamic choice source could not be resolved: instance('remote')",
        "[row : 2] The duplicate name setting is unrelated to survey scope.",
        "[row : 2] Invalid form title metadata, not a survey field name.",
    ],
)
def test_similar_but_unsupported_wording_is_not_forced_to_specific_px_rule(
    monkeypatch, tmp_path, workbook_factory, message
):
    path = workbook_factory(tmp_path / "conservative.xlsx")
    diagnostic = _boundary_diagnostic(
        monkeypatch, path, errors.PyXFormError(message)
    )
    assert diagnostic.rule_id == "PX999"
    assert diagnostic.source.confidence is SourceConfidence.FILE


def test_ordinary_exception_from_convert_boundary_degrades_to_px999(
    monkeypatch, tmp_path, workbook_factory
):
    path = workbook_factory(tmp_path / "ordinary.xlsx")
    diagnostic = _boundary_diagnostic(
        monkeypatch, path, RuntimeError("new supported converter failure shape")
    )
    assert diagnostic.rule_id == "PX999"
    assert diagnostic.message == "pyxform-error: new supported converter failure shape"
    assert diagnostic.source.confidence is SourceConfidence.FILE


@pytest.mark.parametrize("control", [KeyboardInterrupt(), SystemExit(7)])
def test_process_control_exceptions_are_not_normalized(
    monkeypatch, tmp_path, workbook_factory, control
):
    path = workbook_factory(tmp_path / "control.xlsx")

    def interrupt(workbook_bytes: bytes):
        raise control

    monkeypatch.setattr(adapter, "convert_workbook", interrupt)
    with pytest.raises(type(control)):
        adapter.validate_workbook(_bytes(path), str(path))


def test_internal_adapter_failure_outside_convert_boundary_is_not_px999(
    monkeypatch, tmp_path, workbook_factory
):
    path = workbook_factory(tmp_path / "internal.xlsx")

    def upstream_failure(workbook_bytes: bytes):
        raise errors.PyXFormError("unknown upstream shape")

    def internal_bug(workbook_bytes: bytes):
        raise RuntimeError("source index programming failure")

    monkeypatch.setattr(adapter, "convert_workbook", upstream_failure)
    monkeypatch.setattr(adapter, "read_source_index", internal_bug)
    with pytest.raises(RuntimeError, match="source index programming failure"):
        adapter.validate_workbook(_bytes(path), str(path))


def test_first_fatal_is_single_and_native_diagnostics_still_coexist(
    monkeypatch, tmp_path, xlsform_factory
):
    path = xlsform_factory(
        tmp_path / "native-and-fatal.xlsx",
        [SURVEY_HEADER, ("text", "bad name", "")],
    )
    calls = 0

    def first_fatal(workbook_bytes: bytes):
        nonlocal calls
        calls += 1
        raise errors.PyXFormError(
            "[row : 2] On the 'survey' sheet, the 'name' value is invalid. Names "
            "must begin with a letter or underscore. After the first character, "
            "names may contain letters, digits, underscores, hyphens, or periods."
        )

    monkeypatch.setattr(adapter, "convert_workbook", first_fatal)
    diagnostics = lint_workbook(path)
    assert calls == 1
    assert [item.rule_id for item in diagnostics] == ["LBL001", "PX002"]
    assert sum(item.rule_id.startswith("PX") for item in diagnostics) == 1


@pytest.mark.parametrize("container", ["group", "repeat"])
def test_px001_real_duplicate_inside_supported_nested_scope(
    tmp_path, xlsform_factory, container
):
    path = xlsform_factory(
        tmp_path / f"duplicate-in-{container}.xlsx",
        [
            SURVEY_HEADER,
            (f"begin {container}", "container", "Container"),
            ("text", "inside", "One"),
            ("text", "inside", "Two"),
            (f"end {container}", "", ""),
        ],
    )
    px = [item for item in lint_workbook(path) if item.rule_id.startswith("PX")]
    assert len(px) == 1
    assert px[0].rule_id == "PX001"
    assert px[0].source.cell == "B4"
    assert px[0].source.confidence is SourceConfidence.EXACT


@pytest.mark.parametrize(
    ("column_index", "column_name", "expression"),
    [
        (3, "relevant", "${age_yrs} > 17"),
        (4, "constraint", ". > ${age_yrs}"),
        (5, "calculation", "${age_yrs} + 1"),
    ],
)
def test_px005_real_supported_expression_contexts(
    tmp_path, xlsform_factory, column_index, column_name, expression
):
    row = ["integer", "result", "Result", "", "", "", "", ""]
    row[column_index] = expression
    path = xlsform_factory(
        tmp_path / f"unknown-{column_name}.xlsx",
        [SURVEY_HEADER, ("integer", "age_years", "Age"), tuple(row)],
    )
    px = [item for item in lint_workbook(path) if item.rule_id.startswith("PX")]
    assert len(px) == 1
    assert px[0].rule_id == "PX005"
    assert px[0].source.row == 3
    assert px[0].source.column == column_name
    assert px[0].source.confidence is SourceConfidence.EXACT


def test_location_confidence_degrades_from_exact_to_row_sheet_and_file(
    monkeypatch, tmp_path, xlsform_factory
):
    path = xlsform_factory(
        tmp_path / "locations.xlsx",
        [SURVEY_HEADER, ("text", "known", "Known")],
    )
    index = adapter.read_source_index(_bytes(path))

    exact = adapter._best_location(str(path), index, sheet="survey", row=2, column="name")
    row = adapter._best_location(str(path), index, sheet="survey", row=2, column="absent")
    sheet = adapter._best_location(str(path), index, sheet="survey", row=99, column="name")
    file = adapter._best_location(str(path), index, sheet="missing", row=99, column="name")

    assert (exact.confidence, exact.cell) == (SourceConfidence.EXACT, "B2")
    assert (row.confidence, row.sheet, row.row, row.cell) == (
        SourceConfidence.ROW,
        "Survey",
        2,
        None,
    )
    assert (sheet.confidence, sheet.sheet, sheet.row) == (
        SourceConfidence.SHEET,
        "Survey",
        None,
    )
    assert file.confidence is SourceConfidence.FILE


def test_real_corpus_boundary_cases_remain_stable():
    corpus = Path(__file__).parent / "fixtures" / "corpus"
    expected = {
        "findings/duplicate_choice.xlsx": "PX006",
        "malformed/unknown_choice_list.xlsx": "PX004",
        "malformed/unmatched_end_group.xlsx": "PX999",
    }
    for relative, rule_id in expected.items():
        diagnostics = lint_workbook(corpus / relative)
        assert [item.rule_id for item in diagnostics if item.rule_id.startswith("PX")] == [
            rule_id
        ]
