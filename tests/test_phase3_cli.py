from __future__ import annotations

import subprocess
import sys

import pytest


def _run(path):
    return subprocess.run(
        [sys.executable, "-m", "xlsform_lint", str(path)],
        check=False, capture_output=True, text=True,
    )


@pytest.mark.parametrize(
    ("name", "survey_rows", "choices_rows", "rule"),
    [
        ("cho", [("type", "name", "label"), ("text", "q", "Q")],
         [("list_name", "name", "label"), ("unused", "a", "A")], "CHO001"),
        ("lbl1", [("type", "name", "label", "hint"), ("text", "q", None, "Helpful hint")], None, "LBL001"),
        ("lbl2", [("type", "name", "label"), ("select_one list", "q", "Q")],
         [("list_name", "name", "label"), ("list", "a", None)], "LBL002"),
        ("i18n", [("type", "name", "label::English", "label::French"), ("text", "q", "Q", None)], None, "I18N001"),
        ("ux1", [("type", "name", "label", "constraint"), ("integer", "q", "Q", ". > 0")], None, "UX001"),
        ("ord", [("type", "name", "label", "choice_filter"),
                 ("select_one list", "q", "Q", "x=${later}"), ("text", "later", "Later", None)],
         [("list_name", "name", "label"), ("list", "a", "A")], "ORD001"),
        ("ux2", [("type", "name", "label", "required", "default"), ("text", "q", "Q", "yes", "x")], None, "UX002"),
    ],
)
def test_each_native_rule_real_cli_exits_zero(
    tmp_path, xlsform_factory, name, survey_rows, choices_rows, rule
):
    path = xlsform_factory(tmp_path / f"{name}.xlsx", survey_rows, choices_rows=choices_rows)
    result = _run(path)
    assert result.returncode == 0
    assert rule in result.stdout
    assert result.stderr == ""
    assert "Traceback" not in result.stdout


def test_clean_combined_and_native_plus_px_cli(tmp_path, xlsform_factory):
    clean = xlsform_factory(tmp_path / "clean.xlsx", [("type", "name", "label"), ("text", "q", "Q")])
    clean_result = _run(clean)
    assert clean_result.returncode == 0
    assert clean_result.stdout == "0 errors, 0 warnings\n"
    assert clean_result.stderr == ""

    combined = xlsform_factory(
        tmp_path / "combined.xlsx",
        [("type", "name", "label", "hint", "constraint", "required", "default"),
         ("text", "q", None, "Helpful hint", ". != ''", "yes", "x")],
        choices_rows=[("list_name", "name", "label"), ("unused", "a", None)],
    )
    first = _run(combined)
    second = _run(combined)
    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    assert first.stderr == second.stderr == ""
    assert all(rule in first.stdout for rule in ("CHO001", "LBL001", "LBL002", "UX001", "UX002"))
    assert "0 errors, 4 warnings, 1 info" in first.stdout

    mixed = xlsform_factory(
        tmp_path / "native-plus-px.xlsx",
        [("type", "name", "label", "constraint"),
         ("text", "safe", "Safe", ". != ''"), ("text", "1bad", "Bad", None)],
    )
    result = _run(mixed)
    assert result.returncode == 1
    assert "UX001" in result.stdout and "PX002" in result.stdout
    assert "1 error, 1 warning" in result.stdout
    assert result.stderr == ""
