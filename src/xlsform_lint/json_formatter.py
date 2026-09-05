"""Deterministic, versioned JSON serialization of structured diagnostics."""

from __future__ import annotations

import json
from typing import Iterable

from .diagnostics import Diagnostic, SourceLocation, sort_diagnostics, summarize


JSON_OUTPUT_SCHEMA_VERSION = 1


def location_object(location: SourceLocation) -> dict[str, object]:
    """Represent only the source precision already present in the model."""

    return {
        "sheet": location.sheet,
        "row": location.row,
        "column": location.column,
        "cell": location.cell,
        "confidence": location.confidence.value,
    }


def diagnostic_object(diagnostic: Diagnostic) -> dict[str, object]:
    """Convert one diagnostic without parsing human output."""

    return {
        "rule_id": diagnostic.rule_id,
        "severity": str(diagnostic.severity),
        "message": diagnostic.message,
        "origin": diagnostic.origin.value,
        "location": None if diagnostic.source is None else location_object(diagnostic.source),
        "help": diagnostic.help,
        "related": [location_object(location) for location in diagnostic.related],
    }


def json_payload(file: str, diagnostics: Iterable[Diagnostic]) -> dict[str, object]:
    """Build the public JSON V1 object in frozen key order."""

    ordered = sort_diagnostics(diagnostics)
    summary = summarize(ordered)
    return {
        "version": JSON_OUTPUT_SCHEMA_VERSION,
        "file": file,
        "diagnostics": [diagnostic_object(item) for item in ordered],
        "summary": {
            "errors": summary.errors,
            "warnings": summary.warnings,
            "info": summary.info,
        },
    }


def format_json(file: str, diagnostics: Iterable[Diagnostic]) -> str:
    """Emit exactly one UTF-8-friendly JSON document and trailing newline."""

    return json.dumps(json_payload(file, diagnostics), ensure_ascii=False, indent=2) + "\n"
