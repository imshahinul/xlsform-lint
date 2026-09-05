from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import jsonschema
import pytest

from xlsform_lint.diagnostics import (
    Diagnostic, DiagnosticOrigin, Severity, SourceConfidence, SourceLocation,
)
from xlsform_lint.json_formatter import json_payload


SCHEMA_PATH = Path(__file__).parents[1] / "schemas" / "xlsform-lint-output-v1.schema.json"


def _schema() -> dict[str, object]:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    return schema


def _representative_payload() -> dict[str, object]:
    exact = SourceLocation("form.xlsx", "Survey", 9, "constraint", "D9", SourceConfidence.EXACT)
    related = SourceLocation("form.xlsx", "Survey", 2, "name", "B2", SourceConfidence.EXACT)
    diagnostics = (
        Diagnostic("PX999", Severity.ERROR, "PX error", None, DiagnosticOrigin.PYXFORM),
        Diagnostic("UX001", Severity.WARNING, "warning", exact, DiagnosticOrigin.NATIVE, related=(related,)),
        Diagnostic("UX002", Severity.INFO, "info", SourceLocation("form.xlsx"), DiagnosticOrigin.NATIVE),
    )
    return json_payload("form.xlsx", diagnostics)


def test_schema_is_valid_and_accepts_clean_and_representative_outputs() -> None:
    schema = _schema()
    jsonschema.validate(json_payload("form.xlsx", ()), schema)
    jsonschema.validate(_representative_payload(), schema)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda p: p.pop("version"),
        lambda p: p.__setitem__("version", 2),
        lambda p: p["diagnostics"][0].pop("rule_id"),
        lambda p: p["diagnostics"][0].__setitem__("severity", "fatal"),
        lambda p: p["diagnostics"][0].__setitem__("origin", "other"),
        lambda p: p["diagnostics"][1]["location"].__setitem__("confidence", "guess"),
        lambda p: p["diagnostics"][1]["location"].__setitem__("row", 0),
        lambda p: p["summary"].__setitem__("errors", "one"),
        lambda p: p["diagnostics"][0].__setitem__("unexpected", True),
    ],
)
def test_schema_rejects_contract_drift(mutation) -> None:
    payload = deepcopy(_representative_payload())
    mutation(payload)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, _schema())
