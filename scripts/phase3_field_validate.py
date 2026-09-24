"""Run the frozen 0.2.0 engine against the Phase 3.0B field corpus."""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter

from xlsform_lint.engine import lint_workbook


ROOT = Path(__file__).parents[1]
FIELD = ROOT / "tests" / "fixtures" / "field"
MANIFEST = FIELD / "manifest.json"


def source_path(entry: dict[str, object], reference_root: Path | None) -> Path | None:
    if entry["committed"]:
        return FIELD / str(entry["path"])
    if reference_root is None:
        return None
    return reference_root / str(entry["source_path"])


def validate(reference_root: Path | None = None) -> dict[str, object]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    results = []
    aggregate_rules: Counter[str] = Counter()
    adjudication: Counter[str] = Counter()
    for entry in manifest["forms"]:
        path = source_path(entry, reference_root)
        if path is None:
            results.append({"id": entry["id"], "status": "REFERENCE_NOT_PROVIDED"})
            continue
        actual_hash = sha256(path.read_bytes()).hexdigest()
        if actual_hash != entry["sha256"]:
            raise RuntimeError(f"SHA-256 mismatch for {entry['id']}: {actual_hash}")
        started = perf_counter()
        diagnostics = lint_workbook(path)
        elapsed = perf_counter() - started
        counts = Counter(item.rule_id for item in diagnostics)
        expected = Counter(entry["expected_rule_counts"])
        if counts != expected:
            raise RuntimeError(f"diagnostic mismatch for {entry['id']}: {counts} != {expected}")
        expanded = []
        policy = entry["adjudication"]
        for item in diagnostics:
            decision = policy[item.rule_id]
            adjudication[decision["classification"]] += 1
            expanded.append(
                {
                    "rule_id": item.rule_id,
                    "sheet": item.source.sheet,
                    "row": item.source.row,
                    "cell": item.source.cell,
                    "source_confidence": item.source.confidence.value,
                    "classification": decision["classification"],
                    "confidence": decision["confidence"],
                    "rationale": decision["rationale"],
                }
            )
        aggregate_rules.update(counts)
        results.append(
            {
                "id": entry["id"],
                "status": "EXECUTED",
                "runtime_seconds": round(elapsed, 6),
                "diagnostic_count": len(diagnostics),
                "rule_counts": dict(sorted(counts.items())),
                "diagnostics": expanded,
            }
        )
    executed = [item for item in results if item["status"] == "EXECUTED"]
    return {
        "schema": 1,
        "product_version": manifest["product_version"],
        "forms_declared": len(manifest["forms"]),
        "forms_executed": len(executed),
        "source_families": len({entry["source_family"] for entry in manifest["forms"]}),
        "diagnostics": sum(aggregate_rules.values()),
        "rule_counts": dict(sorted(aggregate_rules.items())),
        "adjudication_counts": dict(sorted(adjudication.items())),
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-root", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    report = validate(arguments.reference_root)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
