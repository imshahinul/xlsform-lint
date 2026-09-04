from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path
from typing import Callable

import pytest

from xlsform_lint.cli import main
from xlsform_lint.diagnostics import DiagnosticOrigin, Severity, SourceConfidence
from xlsform_lint.engine import lint_workbook


FATAL_MESSAGE = "pyxform-error: Unknown question type 'definitely_not_a_type'."


def test_real_invalid_workbook_normalizes_to_file_level_px999(
    tmp_path: Path, workbook_factory: Callable[..., Path]
) -> None:
    path = workbook_factory(tmp_path / "fatal.xlsx", question_type="definitely_not_a_type")
    diagnostics = lint_workbook(path)
    assert len(diagnostics) == 1
    diagnostic = diagnostics[0]
    assert diagnostic.rule_id == "PX999"
    assert diagnostic.severity is Severity.ERROR
    assert diagnostic.origin is DiagnosticOrigin.PYXFORM
    assert diagnostic.message == FATAL_MESSAGE
    assert diagnostic.source is not None
    assert diagnostic.source.path == str(path)
    assert diagnostic.source.confidence is SourceConfidence.FILE


def test_cli_valid_and_invalid_are_stable(
    tmp_path: Path,
    workbook_factory: Callable[..., Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    valid = workbook_factory(tmp_path / "valid.xlsx")
    assert main([str(valid)]) == 0
    assert capsys.readouterr().out == "0 errors, 0 warnings\n"

    invalid = workbook_factory(tmp_path / "fatal.xlsx", question_type="definitely_not_a_type")
    assert main([str(invalid)]) == 1
    first = capsys.readouterr()
    assert first.err == ""
    assert first.out == (
        f"{invalid}\nPX999 error {FATAL_MESSAGE}\n\n1 error, 0 warnings\n"
    )
    assert main([str(invalid)]) == 1
    second = capsys.readouterr()
    assert second == first
    assert hashlib.sha256(first.out.encode()).digest() == hashlib.sha256(
        second.out.encode()
    ).digest()


def test_module_cli_bad_usage_returns_two_without_traceback() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "xlsform_lint"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert "usage: xlsform-lint" in completed.stderr
    assert "Traceback" not in completed.stderr


def test_orchestration_acquires_original_path_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    workbook_factory: Callable[..., Path],
) -> None:
    path = workbook_factory(tmp_path / "valid.xlsx")
    real_read = Path.open
    opens = 0

    def counting_open(candidate: Path, *args: object, **kwargs: object):
        nonlocal opens
        if candidate == path:
            opens += 1
        return real_read(candidate, *args, **kwargs)

    monkeypatch.setattr(Path, "open", counting_open)
    assert lint_workbook(path) == ()
    assert opens == 1
