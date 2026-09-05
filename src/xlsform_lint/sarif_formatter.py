"""Deterministic targeted SARIF 2.1.0 serialization for XLSX diagnostics."""

from __future__ import annotations

import json
from typing import Iterable

from .diagnostics import Diagnostic, SourceLocation, sort_diagnostics


SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"
SARIF_VERSION = "2.1.0"
SARIF_LEVELS = {"error": "error", "warning": "warning", "info": "note"}


def _physical_location(file: str, location: SourceLocation) -> dict[str, object]:
    physical: dict[str, object] = {"artifactLocation": {"uri": file}}
    if location.row is not None:
        physical["region"] = {"startLine": location.row}
    return {"physicalLocation": physical}


def _location_properties(location: SourceLocation | None) -> dict[str, object]:
    return {
        "workbookSheet": None if location is None else location.sheet,
        "workbookColumn": None if location is None else location.column,
        "workbookCell": None if location is None else location.cell,
        "locationConfidence": None if location is None else location.confidence.value,
    }


def _related_location(file: str, location: SourceLocation, identifier: int) -> dict[str, object]:
    result = {"id": identifier, **_physical_location(file, location)}
    result["properties"] = _location_properties(location)
    return result


def _result(file: str, diagnostic: Diagnostic) -> dict[str, object]:
    result: dict[str, object] = {
        "ruleId": diagnostic.rule_id,
        "level": SARIF_LEVELS[str(diagnostic.severity)],
        "message": {"text": diagnostic.message},
    }
    if diagnostic.source is not None:
        result["locations"] = [_physical_location(file, diagnostic.source)]
    properties = {
        "origin": diagnostic.origin.value,
        **_location_properties(diagnostic.source),
    }
    if diagnostic.help is not None:
        properties["help"] = diagnostic.help
    result["properties"] = properties
    if diagnostic.related:
        result["relatedLocations"] = [
            _related_location(file, location, index)
            for index, location in enumerate(diagnostic.related, start=1)
        ]
    return result


def sarif_payload(file: str, diagnostics: Iterable[Diagnostic]) -> dict[str, object]:
    """Build one standard SARIF run; XLSX precision remains in properties."""

    ordered = sort_diagnostics(diagnostics)
    levels = {item.rule_id: SARIF_LEVELS[str(item.severity)] for item in ordered}
    rules = [
        {"id": rule_id, "defaultConfiguration": {"level": levels[rule_id]}}
        for rule_id in sorted(levels)
    ]
    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {"driver": {"name": "xlsform-lint", "rules": rules}},
                "results": [_result(file, item) for item in ordered],
            }
        ],
    }


def format_sarif(file: str, diagnostics: Iterable[Diagnostic]) -> str:
    """Emit one SARIF JSON document with exactly one trailing newline."""

    return json.dumps(sarif_payload(file, diagnostics), ensure_ascii=False, indent=2) + "\n"
