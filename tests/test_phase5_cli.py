from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import jsonschema
import pytest

from test_phase5_sarif import validate_sarif_structure


SCHEMA = json.loads(
    (Path(__file__).parents[1] / "schemas" / "xlsform-lint-output-v1.schema.json").read_text(encoding="utf-8")
)


def _run(path: Path, *options: object, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    workbook = path.name if cwd is not None else str(path)
    return subprocess.run(
        [sys.executable, "-m", "xlsform_lint", workbook, *(str(item) for item in options)],
        cwd=cwd, check=False, capture_output=True, text=True, encoding="utf-8",
    )


@pytest.fixture
def phase5_forms(tmp_path: Path, xlsform_factory) -> dict[str, Path]:
    root = tmp_path / "forms"
    root.mkdir()
    clean = xlsform_factory(root / "clean.xlsx", [("type", "name", "label"), ("text", "q", "Question")])
    native = xlsform_factory(
        root / "native.xlsx",
        [("type", "name", "label", "constraint", "required", "default"),
         ("text", "q", "Français éclair", ". != ''", "yes", "value")],
    )
    px = xlsform_factory(
        root / "px.xlsx",
        [("type", "name", "label", "constraint"), ("text", "1bad", "Bad", ". != ''")],
    )
    return {"clean": clean, "native": native, "px": px}


@pytest.mark.parametrize("kind", ["clean", "native", "px"])
@pytest.mark.parametrize("output_format", ["json", "sarif"])
def test_machine_cli_parse_validate_exit_and_repeat_determinism(
    phase5_forms: dict[str, Path], kind: str, output_format: str
) -> None:
    expected_exit = 1 if kind == "px" else 0
    first = _run(phase5_forms[kind], "--format", output_format)
    second = _run(phase5_forms[kind], "--format", output_format)
    assert (first.returncode, first.stdout, first.stderr) == (second.returncode, second.stdout, second.stderr)
    assert first.returncode == expected_exit and first.stderr == ""
    assert first.stdout.endswith("\n") and not first.stdout.endswith("\n\n")
    assert "\x1b" not in first.stdout and "Traceback" not in first.stdout
    payload = json.loads(first.stdout)
    if output_format == "json":
        jsonschema.validate(payload, SCHEMA)
    else:
        validate_sarif_structure(payload)


@pytest.mark.parametrize("output_format", ["json", "sarif"])
def test_hidden_px_is_not_reported_but_exit_remains_one(phase5_forms, output_format: str) -> None:
    result = _run(phase5_forms["px"], "--ignore", "PX", "--format", output_format)
    assert result.returncode == 1 and result.stderr == ""
    payload = json.loads(result.stdout)
    values = payload["diagnostics"] if output_format == "json" else payload["runs"][0]["results"]
    assert all((item.get("rule_id") or item.get("ruleId")) != "PX002" for item in values)


def test_format_precedence_selection_severity_and_strict(phase5_forms) -> None:
    path = phase5_forms["native"]
    config = path.parent / "config.toml"
    config.write_text('[lint]\nformat = "json"\n[rules]\nUX001 = "error"\n', encoding="utf-8")
    configured = _run(path, "--config", config)
    assert configured.returncode == 1
    assert json.loads(configured.stdout)["diagnostics"][0]["severity"] == "error"

    selected = _run(path, "--format", "sarif", "--select", "UX001")
    run = json.loads(selected.stdout)["runs"][0]
    assert [result["ruleId"] for result in run["results"]] == ["UX001"]
    assert [rule["id"] for rule in run["tool"]["driver"]["rules"]] == ["UX001"]

    strict = _run(path, "--format", "sarif", "--select", "UX002", "--profile", "strict")
    default = _run(path, "--format", "sarif", "--select", "UX002")
    assert json.loads(default.stdout)["runs"][0]["results"][0]["level"] == "note"
    assert json.loads(strict.stdout)["runs"][0]["results"][0]["level"] == "warning"

    overridden = _run(path, "--config", config, "--format", "text")
    assert overridden.stdout.startswith(str(path)) and not overridden.stdout.startswith("{")


@pytest.mark.parametrize(
    ("configured", "cli_format", "expected"),
    [
        ("json", "text", "text"),
        ("text", "json", "json"),
        ("sarif", "json", "json"),
        ("json", "sarif", "sarif"),
    ],
)
def test_cli_format_overrides_config_format(phase5_forms, configured, cli_format, expected) -> None:
    path = phase5_forms["clean"]
    config = path.parent / "precedence.toml"
    config.write_text(f'[lint]\nformat = "{configured}"\n', encoding="utf-8")
    result = _run(path, "--config", config, "--format", cli_format)
    assert result.returncode == 0 and result.stderr == ""
    if expected == "text":
        assert result.stdout == "0 errors, 0 warnings\n"
    elif expected == "json":
        assert json.loads(result.stdout)["version"] == 1
    else:
        assert json.loads(result.stdout)["version"] == "2.1.0"


@pytest.mark.parametrize("value", ["text", "json", "sarif"])
def test_config_formats_are_active(phase5_forms, value: str) -> None:
    config = phase5_forms["clean"].parent / f"{value}.toml"
    config.write_text(f'[lint]\nformat = "{value}"\n', encoding="utf-8")
    result = _run(phase5_forms["clean"], "--config", config)
    if value == "text":
        assert result.stdout == "0 errors, 0 warnings\n"
    else:
        assert json.loads(result.stdout)


def test_invalid_cli_format_is_argparse_exit_two(phase5_forms) -> None:
    result = _run(phase5_forms["clean"], "--format", "yaml")
    assert result.returncode == 2 and result.stdout == ""
    assert "invalid choice" in result.stderr and "Traceback" not in result.stderr


def test_invalid_config_format_is_exit_two_without_machine_envelope(phase5_forms) -> None:
    config = phase5_forms["clean"].parent / "invalid.toml"
    config.write_text('[lint]\nformat = "yaml"\n', encoding="utf-8")
    result = _run(phase5_forms["clean"], "--config", config, "--format", "json")
    assert result.returncode == 2 and result.stdout == ""
    assert result.stderr.startswith("xlsform-lint: error:") and "Traceback" not in result.stderr


@pytest.mark.parametrize(
    ("kind", "options", "expected"),
    [
        ("clean", (), 0),
        ("native", ("--fail-on", "warning"), 1),
        ("px", (), 1),
        ("px", ("--ignore", "PX"), 1),
    ],
)
def test_exit_status_is_format_independent(phase5_forms, kind, options, expected) -> None:
    exits = {
        output_format: _run(phase5_forms[kind], *options, "--format", output_format).returncode
        for output_format in ("text", "json", "sarif")
    }
    assert exits == {"text": expected, "json": expected, "sarif": expected}


def test_default_text_is_byte_identical_to_explicit_text(phase5_forms) -> None:
    default = _run(phase5_forms["native"])
    explicit = _run(phase5_forms["native"], "--format", "text")
    assert (default.returncode, default.stdout, default.stderr) == (
        explicit.returncode, explicit.stdout, explicit.stderr
    )


def test_output_format_does_not_add_reads_or_conversions(monkeypatch, phase5_forms, capsys) -> None:
    import xlsform_lint.engine as engine
    from xlsform_lint.cli import main

    reads = conversions = 0
    original_read = engine.read_workbook_bytes
    original_validate = engine.validate_workbook

    def read(path):
        nonlocal reads
        reads += 1
        return original_read(path)

    def validate(workbook, source_path):
        nonlocal conversions
        conversions += 1
        return original_validate(workbook, source_path)

    monkeypatch.setattr(engine, "read_workbook_bytes", read)
    monkeypatch.setattr(engine, "validate_workbook", validate)
    assert main([str(phase5_forms["clean"]), "--format", "json"]) == 0
    assert reads == conversions == 1
    assert json.loads(capsys.readouterr().out)
