from __future__ import annotations

import json

from xlsform_lint.diagnostics import (
    Diagnostic,
    DiagnosticOrigin,
    Severity,
    SourceConfidence,
    SourceLocation,
)
from xlsform_lint.json_formatter import JSON_OUTPUT_SCHEMA_VERSION, format_json, json_payload


def test_json_formatter_preserves_full_structured_contract_and_unicode() -> None:
    source = SourceLocation("form.xlsx", "Survey", 9, "constraint", "D9", SourceConfidence.EXACT)
    related = SourceLocation("form.xlsx", "Survey", 3, "name", "B3", SourceConfidence.EXACT)
    diagnostic = Diagnostic(
        "UX001", Severity.WARNING, "éclair Français", source, DiagnosticOrigin.NATIVE,
        help="Existing help", related=(related,),
    )
    text = format_json("form.xlsx", (diagnostic,))
    payload = json.loads(text)
    assert JSON_OUTPUT_SCHEMA_VERSION == 1
    assert list(payload) == ["version", "file", "diagnostics", "summary"]
    assert list(payload["diagnostics"][0]) == [
        "rule_id", "severity", "message", "origin", "location", "help", "related"
    ]
    assert payload["diagnostics"][0] == {
        "rule_id": "UX001",
        "severity": "warning",
        "message": "éclair Français",
        "origin": "native",
        "location": {
            "sheet": "Survey", "row": 9, "column": "constraint", "cell": "D9",
            "confidence": "exact",
        },
        "help": "Existing help",
        "related": [{
            "sheet": "Survey", "row": 3, "column": "name", "cell": "B3",
            "confidence": "exact",
        }],
    }
    assert payload["summary"] == {"errors": 0, "warnings": 1, "info": 0}
    assert "éclair Français" in text and "\\u00e9" not in text
    assert text.endswith("\n") and not text.endswith("\n\n")


def test_json_unsourced_file_level_and_deterministic_order() -> None:
    unsourced = Diagnostic("PX999", Severity.ERROR, "failure", None, DiagnosticOrigin.PYXFORM)
    file_source = SourceLocation("form.xlsx")
    file_level = Diagnostic("UX002", Severity.INFO, "note", file_source, DiagnosticOrigin.NATIVE)
    first = json_payload("form.xlsx", (file_level, unsourced))
    second = json_payload("form.xlsx", (unsourced, file_level))
    assert first == second
    assert first["diagnostics"][0]["location"] is None
    assert first["diagnostics"][1]["location"] == {
        "sheet": None, "row": None, "column": None, "cell": None, "confidence": "file"
    }
    assert first["diagnostics"][0]["help"] is None


def test_json_uses_effective_severity_without_recalculation() -> None:
    diagnostic = Diagnostic("UX002", Severity.WARNING, "promoted", None, DiagnosticOrigin.NATIVE)
    assert json_payload("form.xlsx", (diagnostic,))["diagnostics"][0]["severity"] == "warning"
