from __future__ import annotations

import pytest

from xlsform_lint.cli import main
from xlsform_lint.diagnostics import Diagnostic, DiagnosticOrigin, Severity, exit_code_for


@pytest.mark.parametrize(
    ("severity", "expected"),
    [(None, 0), (Severity.INFO, 0), (Severity.WARNING, 0), (Severity.ERROR, 1)],
)
def test_default_exit_threshold(severity: Severity | None, expected: int) -> None:
    diagnostics = [] if severity is None else [
        Diagnostic("PX999", severity, "message", None, DiagnosticOrigin.PYXFORM)
    ]
    assert exit_code_for(diagnostics) == expected


def test_bad_input_exits_two(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["does-not-exist.xlsx"]) == 2
    assert capsys.readouterr().err == (
        "xlsform-lint: error: input does not exist: does-not-exist.xlsx\n"
    )


def test_unexpected_internal_failure_exits_three_without_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(_: str) -> tuple[Diagnostic, ...]:
        raise RuntimeError("private detail")

    monkeypatch.setattr("xlsform_lint.cli.lint_workbook", fail)
    assert main(["form.xlsx"]) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "xlsform-lint: internal error\n"
    assert "private detail" not in captured.err
