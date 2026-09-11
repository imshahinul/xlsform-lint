from __future__ import annotations

from collections import Counter

import pytest

from xlsform_lint.diagnostics import Severity, SourceConfidence
from xlsform_lint.engine import lint_workbook


NATIVE_RULE_IDS = {"CHO001", "LBL001", "LBL002", "I18N001", "UX001", "ORD001", "UX002"}


def _native(path):
    return tuple(item for item in lint_workbook(path) if item.rule_id in NATIVE_RULE_IDS)


def _native_ids(path):
    return tuple(item.rule_id for item in _native(path))


@pytest.mark.parametrize("select_type", ["select_one used", "select_multiple used"])
def test_cho001_recognizes_static_lists_amid_realistic_choice_data(tmp_path, xlsform_factory, select_type):
    choices = [("list_name", "name", "label::English", "label::French", "filter_key", "media::image")]
    choices.extend(("used", f"value_{index}", f"Value {index}", f"Valeur {index}", index % 3, None)
                   for index in range(75))
    choices.extend((("overlap", "same", "Same", "Même", 0, None),
                    ("overlap", "other", "Other", "Autre", 1, None)))
    path = xlsform_factory(
        tmp_path / f"cho-{select_type.split('_')[1]}.xlsx",
        [("type", "name", "label::English", "label::French", "choice_filter"),
         (select_type, "selection", "Selection", "Sélection", "filter_key = 1")],
        choices_rows=choices,
    )
    findings = [item for item in _native(path) if item.rule_id == "CHO001"]
    assert len(findings) == 1
    assert "'overlap'" in findings[0].message
    assert findings[0].severity is Severity.WARNING
    assert findings[0].source.confidence is SourceConfidence.EXACT


def test_cho001_suppresses_when_any_select_representation_is_ambiguous(tmp_path, xlsform_factory):
    path = xlsform_factory(
        tmp_path / "cho-ambiguous.xlsx",
        [("type", "name", "label"),
         ("select_one used", "inside", "Inside"),
         ("select_one ${computed_list}", "dynamic", "Dynamic")],
        choices_rows=[("list_name", "name", "label", "extra"),
                      ("used", "yes", "Yes", "retained"),
                      ("possibly_dynamic", "no", "No", "retained")],
    )
    assert "CHO001" not in _native_ids(path)


@pytest.mark.parametrize(
    ("question_type", "expected_lbl001"),
    [("text", True), ("note", True), ("calculate", False), ("hidden", False),
     ("start", False), ("begin group", False), ("end group", False),
     ("begin repeat", False), ("end repeat", False), ("mystery", False)],
)
def test_lbl001_eligibility_boundary(tmp_path, xlsform_factory, question_type, expected_lbl001):
    path = xlsform_factory(
        tmp_path / f"lbl001-{question_type.replace(' ', '-')}.xlsx",
        [("type", "name", "label::English", "label::French"),
         (question_type, "item", None, " ")],
    )
    assert ("LBL001" in _native_ids(path)) is expected_lbl001


def test_lbl001_accepts_label_in_any_supported_translation(tmp_path, xlsform_factory):
    path = xlsform_factory(
        tmp_path / "lbl001-translated.xlsx",
        [("type", "name", "label::English", "label::French", "label::Spanish"),
         ("text", "question", None, "Question", None)],
    )
    ids = _native_ids(path)
    assert "LBL001" not in ids
    assert ids.count("I18N001") == 2


def test_lbl002_is_distinct_from_partial_translation_coverage(tmp_path, xlsform_factory):
    path = xlsform_factory(
        tmp_path / "lbl002-translations.xlsx",
        [("type", "name", "label"), ("select_one colors", "color", "Color")],
        choices_rows=[("list_name", "name", "label::English", "label::French", "other"),
                      ("colors", "red", "Red", None, "x"),
                      ("colors", "blue", " ", "Bleu", "x"),
                      ("colors", "blank", None, " ", "x"),
                      (None, None, None, None, "not a choice")],
    )
    ids = _native_ids(path)
    assert ids.count("LBL002") == 1
    assert ids.count("I18N001") == 2


def test_i18n001_only_checks_labels_on_label_bearing_rows(tmp_path, xlsform_factory):
    path = xlsform_factory(
        tmp_path / "i18n-boundary.xlsx",
        [("type", "name", "label::English", "label::French"),
         ("text", "question", "Question", None),
         ("note", "note", "Read this", "Lisez ceci"),
         ("begin group", "group", "Group", None),
         ("calculate", "calc", "Internal", None),
         ("hidden", "hidden", "Internal", None),
         ("end group", None, None, None)],
    )
    findings = [item for item in _native(path) if item.rule_id == "I18N001"]
    assert [(item.source.row, item.source.column) for item in findings] == [(2, "label::French")]


def test_i18n001_does_not_invent_constraint_message_translation_requirements(tmp_path, xlsform_factory):
    path = xlsform_factory(
        tmp_path / "i18n-optional-fields.xlsx",
        [("type", "name", "label", "constraint", "constraint_message::English",
          "constraint_message::French", "hint::English", "hint::French"),
         ("integer", "age", "Age", ". >= 0", "Non-negative", None, "Years", None)],
    )
    assert "I18N001" not in _native_ids(path)
    assert "UX001" not in _native_ids(path)


def test_ux001_positive_and_legitimate_rows(tmp_path, xlsform_factory):
    path = xlsform_factory(
        tmp_path / "ux001-boundary.xlsx",
        [("type", "name", "label", "constraint", "constraint_message::English",
          "constraint_message::French"),
         ("integer", "missing", "Missing", ". > 0", None, None),
         ("integer", "translated", "Translated", ". > 0", None, "Positif"),
         ("integer", "unconstrained", "Unconstrained", None, None, None),
         ("calculate", "calc", None, "${missing} * 2", None, None),
         ("hidden", "internal", None, ". != ''", None, None),
         ("note", "note", "Read", ". != ''", None, None)],
    )
    findings = [item for item in _native(path) if item.rule_id == "UX001"]
    assert [item.source.row for item in findings] == [2]


@pytest.mark.parametrize(
    ("expression", "should_emit"),
    [("region=${later}", True),
     ("region=${earlier}", False),
     ("region=${current}", False),
     ("region=${laterish}", True),
     ("region='${later}'", True),
     ('region="${later}"', True),
     ("region=${missing}", False),
     ("region=${duplicate}", False),
     ("region=${later} and district=${earlier}", True)],
)
def test_ord001_dependency_resolution_boundaries(tmp_path, xlsform_factory, expression, should_emit):
    path = xlsform_factory(
        tmp_path / f"ord-{abs(hash(expression))}.xlsx",
        [("type", "name", "label", "choice_filter"),
         ("text", "earlier", "Earlier", None),
         ("select_one places", "current", "Current", expression),
         ("text", "later", "Later", None),
         ("text", "laterish", "Later-ish", None),
         ("text", "duplicate", "Duplicate one", None),
         ("text", "duplicate", "Duplicate two", None)],
        choices_rows=[("list_name", "name", "label", "region", "district"),
                      ("places", "one", "One", "north", "east")],
    )
    findings = [item for item in _native(path) if item.rule_id == "ORD001"]
    assert bool(findings) is should_emit
    if should_emit:
        assert len(findings) == 1
        expected_row = 5 if "laterish" in expression else 4
        assert findings[0].related[0].row == expected_row
        assert findings[0].source.confidence is SourceConfidence.EXACT


def test_ord001_is_choice_filter_only_and_suppresses_structural_scope(tmp_path, xlsform_factory):
    path = xlsform_factory(
        tmp_path / "ord-scopes.xlsx",
        [("type", "name", "label", "choice_filter", "relevant", "constraint", "calculation"),
         ("begin group", "outer", "Outer", None, None, None, None),
         ("begin repeat", "items", "Items", None, None, None, None),
         ("select_one places", "place", "Place", "region=${later}", None, None, None),
         ("end repeat", None, None, None, None, None, None),
         ("end group", None, None, None, None, None, None),
         ("text", "other", "Other", None, "${later} != ''", "${later} != ''", "${later}"),
         ("text", "later", "Later", None, None, None, None)],
        choices_rows=[("list_name", "name", "label", "region"), ("places", "one", "One", "north")],
    )
    assert "ORD001" not in _native_ids(path)


def test_ux002_only_applies_to_required_questions_with_nonblank_defaults(tmp_path, xlsform_factory):
    path = xlsform_factory(
        tmp_path / "ux002-boundary.xlsx",
        [("type", "name", "label", "required", "default"),
         ("text", "positive", "Positive", " YES ", "answer"),
         ("text", "no_default", "No default", "yes", " "),
         ("text", "not_required", "Not required", "no", "answer"),
         ("text", "boolean_true", "Boolean true", True, "answer"),
         ("calculate", "calc", None, "yes", "2 + 2"),
         ("hidden", "hidden", None, "yes", "internal"),
         ("note", "note", "Read", "yes", "internal"),
         ("begin group", "group", "Group", "yes", "internal"),
         ("end group", None, None, None, None)],
    )
    findings = [item for item in _native(path) if item.rule_id == "UX002"]
    assert [item.source.row for item in findings] == [2]
    assert findings[0].severity is Severity.INFO


def test_cross_rule_realistic_nested_multilingual_repeat_remains_clean(tmp_path, xlsform_factory):
    choices = [("list_name", "name", "label::English", "label::French", "region")]
    choices.extend(("places", f"place_{index}", f"Place {index}", f"Lieu {index}", "north")
                   for index in range(100))
    path = xlsform_factory(
        tmp_path / "cross-rule-clean.xlsx",
        [("type", "name", "label::English", "label::French", "choice_filter", "constraint",
          "constraint_message::English", "constraint_message::French", "required", "default"),
         ("begin group", "household", "Household", "Ménage", None, None, None, None, None, None),
         ("text", "region", "Region", "Région", None, None, None, None, "yes", None),
         ("begin repeat", "members", "Members", "Membres", None, None, None, None, None, None),
         ("select_one places", "place", "Place", "Lieu", "region=${region}", None, None, None, "yes", None),
         ("integer", "age", "Age", "Âge", None, ". >= 0", "Non-negative", "Non négatif", "yes", None),
         ("calculate", "age2", None, None, None, None, None, None, None, "${age} * 2"),
         ("hidden", "internal", None, None, None, None, None, None, None, "seed"),
         ("note", "guidance", "Check answers", "Vérifiez les réponses", None, None, None, None, None, None),
         ("end repeat", None, None, None, None, None, None, None, None, None),
         ("end group", None, None, None, None, None, None, None, None, None),
         ("text", "optional_default", "Optional", "Facultatif", None, None, None, None, "no", "suggested")],
        choices_rows=choices,
    )
    assert _native(path) == ()


def test_cross_rule_positive_control_preserves_every_native_rule(tmp_path, xlsform_factory):
    path = xlsform_factory(
        tmp_path / "cross-rule-positive.xlsx",
        [("type", "name", "label::English", "label::French", "choice_filter", "constraint",
          "constraint_message", "required", "default"),
         ("select_one used", "bad", None, None, "region=${later}", ". != ''", None, "yes", "x"),
         ("text", "later", "Later", "Plus tard", None, None, None, None, None),
         ("text", "incomplete", "English only", None, None, None, None, None, None)],
        choices_rows=[("list_name", "name", "label::English", "label::French", "region"),
                      ("used", "blank", None, None, "north"),
                      ("unused", "ok", "OK", "D'accord", "north")],
    )
    counts = Counter(_native_ids(path))
    assert set(counts) == NATIVE_RULE_IDS
    assert all(counts[rule_id] >= 1 for rule_id in NATIVE_RULE_IDS)
