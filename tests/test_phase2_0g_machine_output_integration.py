from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import jsonschema
import pytest

from xlsform_lint import pre_commit
from xlsform_lint.config import RULE_CATALOG
from xlsform_lint.diagnostics import (
    Diagnostic,
    DiagnosticOrigin,
    Severity,
    SourceConfidence,
    SourceLocation,
)
from xlsform_lint.json_formatter import format_json
from xlsform_lint.sarif_formatter import format_sarif
from xlsform_lint.text_formatter import format_diagnostics


ROOT = Path(__file__).parents[1]
CORPUS = ROOT / "tests" / "fixtures" / "corpus"
SCHEMA = json.loads(
    (ROOT / "schemas" / "xlsform-lint-output-v1.schema.json").read_text(encoding="utf-8")
)
PUBLIC_RULE_IDS = frozenset(RULE_CATALOG)
CORPUS_CASES = (
    ("valid/basic_clean.xlsx", (), 0),
    ("valid/complex_combined.xlsx", (), 0),
    (
        "findings/mixed_native_findings.xlsx",
        ("UX001", "I18N001", "UX002", "ORD001", "LBL001", "LBL002", "CHO001"),
        0,
    ),
    ("findings/duplicate_choice.xlsx", ("PX006",), 1),
    ("malformed/unmatched_end_group.xlsx", ("PX999",), 1),
    ("malformed/unknown_choice_list.xlsx", ("PX004",), 1),
)


def _run(path: Path, output_format: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "xlsform_lint", str(path), "--format", output_format],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _text_rule_ids(output: str) -> tuple[str, ...]:
    return tuple(
        fields[0]
        for line in output.splitlines()
        if (fields := line.split()) and fields[0] in PUBLIC_RULE_IDS
    )


def _structured_rule_ids(output_format: str, output: str) -> tuple[str, ...]:
    payload = json.loads(output)
    if output_format == "json":
        jsonschema.validate(payload, SCHEMA)
        assert payload["version"] == 1
        return tuple(item["rule_id"] for item in payload["diagnostics"])
    assert payload["version"] == "2.1.0"
    run = payload["runs"][0]
    assert run["tool"]["driver"]["name"] == "xlsform-lint"
    assert [rule["id"] for rule in run["tool"]["driver"]["rules"]] == sorted(
        {result["ruleId"] for result in run["results"]}
    )
    return tuple(item["ruleId"] for item in run["results"])


@pytest.mark.parametrize(("relative_path", "expected_ids", "expected_exit"), CORPUS_CASES)
def test_phase2_corpus_text_json_sarif_parity_schema_and_five_run_determinism(
    relative_path: str, expected_ids: tuple[str, ...], expected_exit: int
) -> None:
    path = CORPUS / relative_path
    observed: dict[str, tuple[str, ...]] = {}
    for output_format in ("text", "json", "sarif"):
        repeated = tuple(_run(path, output_format) for _ in range(5))
        assert len({(item.returncode, item.stdout, item.stderr) for item in repeated}) == 1
        result = repeated[0]
        assert result.returncode == expected_exit
        assert result.stderr == ""
        observed[output_format] = (
            _text_rule_ids(result.stdout)
            if output_format == "text"
            else _structured_rule_ids(output_format, result.stdout)
        )
    assert observed == {output_format: expected_ids for output_format in ("text", "json", "sarif")}


def _diagnostic_matrix() -> tuple[Diagnostic, ...]:
    related = SourceLocation(
        "forms\\portable.xlsx", "survey", 2, "name", "B2", SourceConfidence.EXACT
    )
    return (
        Diagnostic(
            "PX001",
            Severity.ERROR,
            "duplicate name",
            SourceLocation("forms\\portable.xlsx", "survey", 5, "name", "B5", SourceConfidence.EXACT),
            DiagnosticOrigin.PYXFORM,
            related=(related,),
        ),
        Diagnostic(
            "ORD001",
            Severity.WARNING,
            "later dependency",
            SourceLocation("forms/portable.xlsx", "survey", 4, confidence=SourceConfidence.ROW),
            DiagnosticOrigin.NATIVE,
            related=(related,),
        ),
        Diagnostic(
            "PX999",
            Severity.ERROR,
            "unknown converter failure",
            SourceLocation("forms/portable.xlsx", confidence=SourceConfidence.FILE),
            DiagnosticOrigin.PYXFORM,
        ),
    )


def test_locations_related_metadata_and_conservative_sarif_precision_are_stable() -> None:
    diagnostics = _diagnostic_matrix()
    json_output = format_json("forms/portable.xlsx", reversed(diagnostics))
    sarif_output = format_sarif("forms/portable.xlsx", reversed(diagnostics))
    text_output = format_diagnostics(reversed(diagnostics))
    assert json_output == format_json("forms/portable.xlsx", diagnostics)
    assert sarif_output == format_sarif("forms/portable.xlsx", diagnostics)
    assert text_output == format_diagnostics(diagnostics)

    payload = json.loads(json_output)
    jsonschema.validate(payload, SCHEMA)
    for item in payload["diagnostics"]:
        metadata = RULE_CATALOG[item["rule_id"]]
        assert item["origin"] == metadata.origin
        if item["rule_id"].startswith("PX"):
            assert item["severity"] == metadata.default_severity
    sarif_results = json.loads(sarif_output)["runs"][0]["results"]
    px999 = next(item for item in sarif_results if item["ruleId"] == "PX999")
    assert px999["properties"]["locationConfidence"] == "file"
    assert "region" not in px999["locations"][0]["physicalLocation"]
    exact = next(item for item in sarif_results if item["ruleId"] == "PX001")
    assert exact["locations"][0]["physicalLocation"]["region"] == {"startLine": 5}
    assert exact["relatedLocations"][0]["physicalLocation"]["region"] == {"startLine": 2}
    assert all(
        item["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
        == "forms/portable.xlsx"
        for item in sarif_results
    )


@pytest.mark.parametrize(
    ("results", "expected"),
    [
        ((0,), 0),
        ((1,), 1),
        ((2,), 2),
        ((0, 0), 0),
        ((0, 1), 1),
        ((1, 2), 2),
        ((2, 3), 3),
        ((0, 1, 2, 3), 3),
    ],
)
def test_precommit_continues_all_files_and_aggregate_is_order_independent(
    monkeypatch: pytest.MonkeyPatch, results: tuple[int, ...], expected: int
) -> None:
    def invoke(order: tuple[int, ...]) -> tuple[int, list[tuple[str, ...]]]:
        pending = iter(order)
        calls: list[tuple[str, ...]] = []

        def fake_cli(arguments: tuple[str, ...]) -> int:
            calls.append(arguments)
            return next(pending)

        monkeypatch.setattr(pre_commit, "cli_main", fake_cli)
        filenames = tuple(f"form-{index}.xlsx" for index in range(len(order)))
        return pre_commit.main(filenames), calls

    forward, forward_calls = invoke(results)
    reverse, reverse_calls = invoke(tuple(reversed(results)))
    expected_calls = [(f"form-{index}.xlsx",) for index in range(len(results))]
    assert (forward, reverse) == (expected, expected)
    assert forward_calls == reverse_calls == expected_calls


def test_published_hook_runtime_processes_clean_finding_and_input_error() -> None:
    clean = CORPUS / "valid" / "basic_clean.xlsx"
    finding = CORPUS / "findings" / "duplicate_choice.xlsx"
    missing = CORPUS / "missing.xlsx"
    result = subprocess.run(
        [sys.executable, "-m", "xlsform_lint.pre_commit", str(clean), str(finding), str(missing)],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 2
    assert str(finding) in result.stdout and "PX006 error" in result.stdout
    assert result.stdout.count("0 errors, 0 warnings") == 1
    assert result.stderr.startswith("xlsform-lint: error:")
    assert str(missing) in result.stderr


def test_hook_metadata_passes_matching_xlsx_filenames_to_adapter() -> None:
    metadata = (ROOT / ".pre-commit-hooks.yaml").read_text(encoding="utf-8")
    assert "- id: xlsform-lint\n" in metadata
    assert "  entry: python -m xlsform_lint.pre_commit\n" in metadata
    assert "  language: python\n" in metadata
    assert "  files: \\.xlsx$\n" in metadata
    assert "  types: [file]\n" in metadata
    assert "pass_filenames: false" not in metadata
