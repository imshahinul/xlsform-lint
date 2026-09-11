from __future__ import annotations

import io
import json
from pathlib import Path
import zipfile

import pytest
from openpyxl import Workbook
from pyxform import errors

from xlsform_lint import pre_commit, pyxform_adapter
from xlsform_lint.cli import main
from xlsform_lint.diagnostics import Diagnostic, DiagnosticOrigin, Severity, SourceLocation


def _diagnostic(rule_id: str = "PX999") -> Diagnostic:
    return Diagnostic(
        rule_id,
        Severity.ERROR,
        "controlled finding",
        SourceLocation("form.xlsx"),
        DiagnosticOrigin.PYXFORM,
    )


def _minimal_workbook(path: Path, *, survey: bool = True, headers: tuple[object, ...] | None = None) -> Path:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "survey" if survey else "notes"
    if headers is not None:
        worksheet.append(headers)
        worksheet.append(("text", "question", "Question"))
    elif survey:
        worksheet.append(("type", "name", "label"))
        worksheet.append(("text", "question", "Question"))
    workbook.save(path)
    workbook.close()
    return path


@pytest.mark.parametrize(
    ("make_input", "expected_exit"),
    [
        (lambda path: path, 2),
        (lambda path: path.write_bytes(b"") or path, 2),
        (lambda path: path.write_text("not an xlsx", encoding="utf-8") or path, 2),
        (lambda path: path.write_bytes(b"PK\x03\x04truncated") or path, 2),
    ],
    ids=("missing", "empty", "plain-text", "truncated-zip"),
)
def test_unusable_input_is_exit_2_without_fake_diagnostics(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], make_input, expected_exit: int
) -> None:
    path = tmp_path / "input.xlsx"
    result = make_input(path)

    assert main([str(result)]) == expected_exit
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("xlsform-lint: error:")
    assert "PX" not in captured.err and "Traceback" not in captured.err


def test_zip_that_is_not_a_workbook_is_exit_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "not-workbook.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("payload.txt", "not Office Open XML")

    assert main([str(path)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("xlsform-lint: error: unable to read XLSX input:")


@pytest.mark.parametrize(
    "path_factory",
    [
        lambda path: _minimal_workbook(path, survey=False),
        lambda path: _minimal_workbook(path, headers=("wrong", "headers", "only")),
    ],
    ids=("missing-survey", "malformed-header"),
)
def test_readable_semantically_invalid_workbook_remains_a_finding(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], path_factory
) -> None:
    path = path_factory(tmp_path / "semantic.xlsx")

    assert main([str(path)]) == 1
    captured = capsys.readouterr()
    assert "PX" in captured.out
    assert captured.err == ""


@pytest.mark.parametrize(
    ("contents", "stable_message"),
    [
        ("profile = 1\n", "profile must be one of"),
        ('profile = "unknown"\n', "profile must be one of"),
        ('[select]\ninclude = ["UNKNOWN"]\n', "unknown selector"),
        ('[rules]\nUNKNOWN = "warning"\n', "unknown rule ID"),
        ('[lint]\nfail_on = "fatal"\n', "lint.fail_on must be one of"),
        ('[lint]\nformat = "yaml"\n', "lint.format must be one of"),
        ('lint = "wrong-type"\n', "lint must be a table"),
        ('[broken\n', "unable to load configuration"),
    ],
)
def test_config_taxonomy_is_consistent_exit_2(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    contents: str,
    stable_message: str,
) -> None:
    config = tmp_path / "bad.toml"
    config.write_text(contents, encoding="utf-8")

    assert main(["unused.xlsx", "--config", str(config)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("xlsform-lint: error:")
    assert stable_message in captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("option", ["--select", "--ignore"])
def test_invalid_cli_selector_is_exit_2(
    capsys: pytest.CaptureFixture[str], option: str
) -> None:
    assert main(["unused.xlsx", option, "UX*"]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("xlsform-lint: error:")


@pytest.mark.parametrize(
    "arguments",
    [
        ("unused.xlsx", "--profile", "unknown"),
        ("unused.xlsx", "--fail-on", "fatal"),
        ("unused.xlsx", "--format", "yaml"),
    ],
)
def test_invalid_argparse_choices_preserve_usage_exit_2(
    capsys: pytest.CaptureFixture[str], arguments: tuple[str, ...]
) -> None:
    with pytest.raises(SystemExit) as captured_exit:
        main(arguments)
    assert captured_exit.value.code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "usage: xlsform-lint" in captured.err


@pytest.mark.parametrize(
    ("output_format", "formatter_name"),
    [("text", "format_diagnostics"), ("json", "format_json"), ("sarif", "format_sarif")],
)
def test_formatter_bug_is_internal_exit_3_and_machine_safe(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    output_format: str,
    formatter_name: str,
) -> None:
    monkeypatch.setattr("xlsform_lint.cli.lint_workbook", lambda _: (_diagnostic(),))

    def fail(*_: object) -> str:
        raise RuntimeError("private formatter detail")

    monkeypatch.setattr(f"xlsform_lint.cli.{formatter_name}", fail)
    assert main(["form.xlsx", "--format", output_format]) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "xlsform-lint: internal error\n"
    assert "private formatter detail" not in captured.err


@pytest.mark.parametrize("output_format", ["text", "json", "sarif"])
def test_successful_formats_preserve_normal_exit_1(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    output_format: str,
) -> None:
    monkeypatch.setattr("xlsform_lint.cli.lint_workbook", lambda _: (_diagnostic(),))
    assert main(["form.xlsx", "--format", output_format]) == 1
    captured = capsys.readouterr()
    assert captured.err == ""
    if output_format == "json":
        assert json.loads(captured.out)["version"] == 1
    elif output_format == "sarif":
        assert json.loads(captured.out)["version"] == "2.1.0"
    else:
        assert "PX999 error" in captured.out


def test_native_rule_bug_is_internal_exit_3(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _minimal_workbook(tmp_path / "native.xlsx")

    def fail(*_: object) -> tuple[Diagnostic, ...]:
        raise RuntimeError("native implementation bug")

    monkeypatch.setattr("xlsform_lint.engine.run_native_rules", fail)
    assert main([str(path)]) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "xlsform-lint: internal error\n"


def test_post_converter_internal_bug_is_not_px999(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _minimal_workbook(tmp_path / "post-converter.xlsx")
    monkeypatch.setattr("xlsform_lint.engine.validate_workbook", lambda *_: None)

    def fail(*_: object) -> tuple[Diagnostic, ...]:
        raise RuntimeError("diagnostic sorting bug")

    monkeypatch.setattr("xlsform_lint.engine.sort_diagnostics", fail)
    assert main([str(path)]) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "xlsform-lint: internal error\n"
    assert "PX999" not in captured.out + captured.err


def test_unknown_converter_exception_remains_px999_exit_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _minimal_workbook(tmp_path / "converter.xlsx")

    def fail(_: bytes) -> None:
        raise RuntimeError("supported converter boundary failure")

    monkeypatch.setattr(pyxform_adapter, "convert_workbook", fail)
    assert main([str(path)]) == 1
    captured = capsys.readouterr()
    assert "PX999 error" in captured.out
    assert captured.err == ""


def test_known_pyxform_failure_remains_semantic_exit_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _minimal_workbook(tmp_path / "known.xlsx")

    def fail(_: bytes) -> None:
        raise errors.PyXFormError(
            "[row : 2] On the 'survey' sheet, the 'name' value is invalid. Names must "
            "begin with a letter or underscore. After the first character, names may "
            "contain letters, digits, underscores, hyphens, or periods."
        )

    monkeypatch.setattr(pyxform_adapter, "convert_workbook", fail)
    assert main([str(path)]) == 1
    captured = capsys.readouterr()
    assert "PX002 error" in captured.out
    assert captured.err == ""


@pytest.mark.parametrize("control", [KeyboardInterrupt(), SystemExit(9)])
def test_process_control_exceptions_cross_cli_unchanged(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, control: BaseException
) -> None:
    path = _minimal_workbook(tmp_path / "control.xlsx")

    def stop(_: bytes) -> None:
        raise control

    monkeypatch.setattr(pyxform_adapter, "convert_workbook", stop)
    with pytest.raises(type(control)) as captured:
        main([str(path)])
    if isinstance(control, SystemExit):
        assert captured.value.code == 9


@pytest.mark.parametrize(
    ("results", "expected"),
    [
        ((0, 0), 0),
        ((0, 1), 1),
        ((1, 2), 2),
        ((1, 3), 3),
        ((2, 3), 3),
        ((0, 1, 2, 3), 3),
    ],
)
def test_multifile_priority_is_order_independent(
    monkeypatch: pytest.MonkeyPatch, results: tuple[int, ...], expected: int
) -> None:
    def run(order: tuple[int, ...]) -> int:
        pending = iter(order)
        monkeypatch.setattr(pre_commit, "cli_main", lambda _: next(pending))
        return pre_commit.main(tuple(f"form-{index}.xlsx" for index in range(len(order))))

    assert run(results) == expected
    assert run(tuple(reversed(results))) == expected


def test_stdout_write_bug_is_internal_exit_3(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("xlsform_lint.cli.lint_workbook", lambda _: ())

    class BrokenStdout(io.StringIO):
        def write(self, _: str) -> int:
            raise RuntimeError("output channel bug")

    stdout = BrokenStdout()
    stderr = io.StringIO()
    monkeypatch.setattr("xlsform_lint.cli.sys.stdout", stdout)
    monkeypatch.setattr("xlsform_lint.cli.sys.stderr", stderr)
    assert main(["form.xlsx", "--format", "json"]) == 3
    assert stdout.getvalue() == ""
    assert stderr.getvalue() == "xlsform-lint: internal error\n"
