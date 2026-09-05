from __future__ import annotations

from xlsform_lint.diagnostics import (
    Diagnostic, DiagnosticOrigin, Severity, SourceConfidence, SourceLocation,
)
from xlsform_lint.sarif_formatter import SARIF_SCHEMA, SARIF_VERSION, format_sarif, sarif_payload


def _diagnostic(rule_id: str, severity: Severity, source=None, *, related=(), help=None):
    return Diagnostic(rule_id, severity, f"message {rule_id}", source, DiagnosticOrigin.NATIVE, help, related)


def validate_sarif_structure(payload: dict[str, object]) -> None:
    assert payload["$schema"] == SARIF_SCHEMA
    assert payload["version"] == SARIF_VERSION == "2.1.0"
    assert len(payload["runs"]) == 1
    run = payload["runs"][0]
    assert run["tool"]["driver"]["name"] == "xlsform-lint"
    assert [rule["id"] for rule in run["tool"]["driver"]["rules"]] == sorted(
        {result["ruleId"] for result in run["results"]}
    )
    assert all(result["level"] in {"error", "warning", "note"} for result in run["results"])


def test_sarif_severity_rule_message_location_help_and_related_contract() -> None:
    exact = SourceLocation("ignored.xlsx", "Survey", 9, "constraint", "D9", SourceConfidence.EXACT)
    related = SourceLocation("ignored.xlsx", "Survey", 3, "name", "B3", SourceConfidence.EXACT)
    diagnostics = (
        _diagnostic("UX002", Severity.INFO),
        _diagnostic("PX999", Severity.ERROR, SourceLocation("ignored.xlsx")),
        _diagnostic("UX001", Severity.WARNING, exact, related=(related,), help="Existing help"),
    )
    payload = sarif_payload("form.xlsx", diagnostics)
    validate_sarif_structure(payload)
    results = payload["runs"][0]["results"]
    assert [result["level"] for result in results] == ["note", "warning", "error"]
    warning = results[1]
    assert warning["ruleId"] == "UX001" and warning["message"] == {"text": "message UX001"}
    assert warning["locations"] == [{"physicalLocation": {
        "artifactLocation": {"uri": "form.xlsx"}, "region": {"startLine": 9}
    }}]
    assert warning["properties"] == {
        "origin": "native", "workbookSheet": "Survey", "workbookColumn": "constraint",
        "workbookCell": "D9", "locationConfidence": "exact", "help": "Existing help",
    }
    assert warning["relatedLocations"][0]["id"] == 1
    assert warning["relatedLocations"][0]["physicalLocation"]["region"] == {"startLine": 3}
    assert "locations" not in results[0]
    assert "region" not in results[2]["locations"][0]["physicalLocation"]


def test_sarif_clean_and_deterministic_rules_results_and_newline() -> None:
    assert sarif_payload("form.xlsx", ())["runs"][0]["tool"]["driver"]["rules"] == []
    assert sarif_payload("form.xlsx", ())["runs"][0]["results"] == []
    a = _diagnostic("UX002", Severity.INFO)
    b = _diagnostic("UX001", Severity.WARNING)
    assert sarif_payload("form.xlsx", (a, b)) == sarif_payload("form.xlsx", (b, a))
    text = format_sarif("form.xlsx", (a, b))
    assert text.endswith("\n") and not text.endswith("\n\n")
