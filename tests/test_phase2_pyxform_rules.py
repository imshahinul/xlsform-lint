from __future__ import annotations

from pathlib import Path

import pytest

from xlsform_lint.diagnostics import (
    DiagnosticOrigin,
    Severity,
    SourceConfidence,
)
from xlsform_lint.engine import lint_workbook
from xlsform_lint.pyxform_adapter import suggest_field_name


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


def _lint(path: Path):
    return lint_workbook(path)


def _assert_rule(path: Path, rule_id: str):
    diagnostics = _lint(path)
    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.rule_id == rule_id
    assert diagnostic.severity is Severity.ERROR
    assert diagnostic.origin is DiagnosticOrigin.PYXFORM
    return diagnostic


def test_px001_duplicate_name_has_exact_source_and_unambiguous_related(
    tmp_path, xlsform_factory
):
    path = xlsform_factory(
        tmp_path / "duplicate.xlsx",
        [
            SURVEY_HEADER,
            ("text", "household_id", "First"),
            ("integer", "household_id", "Second"),
        ],
        survey_title="SuRvEy",
    )
    diagnostic = _assert_rule(path, "PX001")
    assert diagnostic.message == (
        "duplicate-name-in-scope: 'household_id' duplicates another name in the "
        "same XLSForm scope."
    )
    assert diagnostic.source.sheet == "SuRvEy"
    assert (diagnostic.source.row, diagnostic.source.column, diagnostic.source.cell) == (
        3,
        "name",
        "B3",
    )
    assert diagnostic.source.confidence is SourceConfidence.EXACT
    assert len(diagnostic.related) == 1
    assert diagnostic.related[0].cell == "B2"


def test_px001_same_name_in_separate_scopes_is_accepted(tmp_path, xlsform_factory):
    path = xlsform_factory(
        tmp_path / "scoped.xlsx",
        [
            SURVEY_HEADER,
            ("begin group", "one", "One"),
            ("text", "same", "First"),
            ("end group", "", ""),
            ("begin group", "two", "Two"),
            ("text", "same", "Second"),
            ("end group", "", ""),
        ],
    )
    assert _lint(path) == ()


def test_px002_invalid_name_and_unusual_valid_control(tmp_path, xlsform_factory):
    invalid = xlsform_factory(
        tmp_path / "invalid-name.xlsx",
        [SURVEY_HEADER, ("text", "bad name", "Bad")],
    )
    diagnostic = _assert_rule(invalid, "PX002")
    assert diagnostic.message == (
        "invalid-survey-name: 'bad name' is not a valid XLSForm field name."
    )
    assert diagnostic.source.cell == "B2"
    assert diagnostic.source.confidence is SourceConfidence.EXACT

    valid = xlsform_factory(
        tmp_path / "unusual-name.xlsx",
        [SURVEY_HEADER, ("text", "éclair-name.ok", "Valid")],
    )
    assert _lint(valid) == ()


@pytest.mark.parametrize(
    ("row", "column"),
    [
        (("", "orphan", "No type"), "type"),
        (("text", "", "No name"), "name"),
    ],
)
def test_px003_missing_structural_value_uses_row_precision(
    tmp_path, xlsform_factory, row, column
):
    path = xlsform_factory(tmp_path / f"missing-{column}.xlsx", [SURVEY_HEADER, row])
    diagnostic = _assert_rule(path, "PX003")
    assert diagnostic.message == (
        f"missing-required-structural-value: required '{column}' value is missing."
    )
    assert diagnostic.source.row == 2
    assert diagnostic.source.confidence is SourceConfidence.ROW


def test_px003_valid_control(tmp_path, xlsform_factory):
    path = xlsform_factory(
        tmp_path / "structural-valid.xlsx", [SURVEY_HEADER, ("text", "named", "Named")]
    )
    assert _lint(path) == ()


def test_px004_missing_list_and_valid_list_control(tmp_path, xlsform_factory):
    missing = xlsform_factory(
        tmp_path / "missing-list.xlsx",
        [SURVEY_HEADER, ("select_one region_list", "region", "Region")],
        choices_rows=[CHOICES_HEADER, ("other_list", "other", "Other")],
    )
    diagnostic = _assert_rule(missing, "PX004")
    assert diagnostic.message == (
        "unknown-internal-choice-list: internal choice list 'region_list' does not exist."
    )
    assert diagnostic.source.cell == "A2"
    assert diagnostic.source.confidence is SourceConfidence.EXACT

    valid = xlsform_factory(
        tmp_path / "valid-list.xlsx",
        [SURVEY_HEADER, ("select_one region_list", "region", "Region")],
        choices_rows=[CHOICES_HEADER, ("region_list", "north", "North")],
    )
    assert _lint(valid) == ()


def test_px005_unknown_reference_suggests_and_maps_actual_cell(tmp_path, xlsform_factory):
    path = xlsform_factory(
        tmp_path / "unknown-reference.xlsx",
        [
            SURVEY_HEADER,
            ("integer", "age_years", "Age"),
            ("text", "adult", "Adult", "${age_yrs} > 17"),
        ],
    )
    diagnostic = _assert_rule(path, "PX005")
    assert diagnostic.message == (
        "unknown-field-reference: 'age_yrs' does not exist. Did you mean 'age_years'?"
    )
    assert (diagnostic.source.row, diagnostic.source.column, diagnostic.source.cell) == (
        3,
        "relevant",
        "D3",
    )
    assert diagnostic.source.confidence is SourceConfidence.EXACT


def test_px005_valid_reference_control(tmp_path, xlsform_factory):
    path = xlsform_factory(
        tmp_path / "valid-reference.xlsx",
        [
            SURVEY_HEADER,
            ("integer", "age_years", "Age"),
            ("text", "adult", "Adult", "${age_years} > 17"),
        ],
    )
    assert _lint(path) == ()


def test_px005_suggestion_is_conservative_unique_and_order_independent():
    assert suggest_field_name("age_yrs", ("person", "age_years")) == "age_years"
    assert suggest_field_name("zzzz", ("person", "age_years")) is None
    assert suggest_field_name("cat", ("bat", "hat"), threshold=0.60) is None
    assert suggest_field_name("age_yrs", ("person", "age_years")) == suggest_field_name(
        "age_yrs", ("age_years", "person")
    )
    assert suggest_field_name("missing", ("other", "field")) is None


def test_px006_duplicate_and_allow_choice_duplicates_real_path(tmp_path, xlsform_factory):
    survey = [SURVEY_HEADER, ("select_one regions", "region", "Region")]
    choices = [
        CHOICES_HEADER,
        ("regions", "north", "North"),
        ("regions", "north", "North again"),
    ]
    duplicate = xlsform_factory(
        tmp_path / "duplicate-choice.xlsx",
        survey,
        choices_rows=choices,
        choices_title="ChOiCeS",
    )
    diagnostic = _assert_rule(duplicate, "PX006")
    assert diagnostic.message == (
        "duplicate-choice-value: 'north' duplicates another choice name in its list."
    )
    assert diagnostic.source.sheet == "ChOiCeS"
    assert diagnostic.source.cell == "B3"
    assert diagnostic.source.confidence is SourceConfidence.EXACT
    assert diagnostic.related[0].cell == "B2"

    allowed = xlsform_factory(
        tmp_path / "allowed-duplicate-choice.xlsx",
        survey,
        choices_rows=choices,
        settings_rows=[
            ("form_title", "form_id", "allow_choice_duplicates"),
            ("Allowed", "allowed", "yes"),
        ],
    )
    assert _lint(allowed) == ()


def test_px006_unique_control(tmp_path, xlsform_factory):
    path = xlsform_factory(
        tmp_path / "unique-choice.xlsx",
        [SURVEY_HEADER, ("select_one regions", "region", "Region")],
        choices_rows=[
            CHOICES_HEADER,
            ("regions", "north", "North"),
            ("regions", "south", "South"),
        ],
    )
    assert _lint(path) == ()


def test_unrecognized_upstream_failure_remains_px999(tmp_path, xlsform_factory):
    path = xlsform_factory(
        tmp_path / "unmatched-end.xlsx", [SURVEY_HEADER, ("end group", "", "")]
    )
    diagnostic = _assert_rule(path, "PX999")
    assert "Unmatched 'end_group'" in diagnostic.message
    assert diagnostic.source.confidence is SourceConfidence.FILE


def test_each_recognized_rule_is_deterministic(tmp_path, xlsform_factory):
    paths = [
        xlsform_factory(
            tmp_path / "p1.xlsx",
            [SURVEY_HEADER, ("text", "dup", "A"), ("text", "dup", "B")],
        ),
        xlsform_factory(tmp_path / "p2.xlsx", [SURVEY_HEADER, ("text", "bad name", "A")]),
        xlsform_factory(tmp_path / "p3.xlsx", [SURVEY_HEADER, ("text", "", "A")]),
        xlsform_factory(
            tmp_path / "p4.xlsx",
            [SURVEY_HEADER, ("select_one missing", "q", "Q")],
            choices_rows=[CHOICES_HEADER, ("other", "x", "X")],
        ),
        xlsform_factory(
            tmp_path / "p5.xlsx",
            [SURVEY_HEADER, ("text", "known_name", "K"), ("text", "q", "Q", "${known_nam}")],
        ),
        xlsform_factory(
            tmp_path / "p6.xlsx",
            [SURVEY_HEADER, ("select_one list", "q", "Q")],
            choices_rows=[CHOICES_HEADER, ("list", "x", "X"), ("list", "x", "X2")],
        ),
    ]
    for path in paths:
        assert _lint(path) == _lint(path)
