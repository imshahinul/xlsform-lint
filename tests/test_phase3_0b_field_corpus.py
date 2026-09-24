from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from scripts.phase3_field_validate import validate


FIELD = Path(__file__).parent / "fixtures" / "field"
MANIFEST = json.loads((FIELD / "manifest.json").read_text(encoding="utf-8"))
FORMS = MANIFEST["forms"]


def test_field_manifest_scope_provenance_and_redistribution_gate():
    assert MANIFEST["product_version"] == "0.2.0"
    assert len(FORMS) == 20
    assert len({entry["id"] for entry in FORMS}) == 20
    assert len({entry["source_family"] for entry in FORMS}) == 3
    assert {entry["classification"] for entry in FORMS} == {"SAFE_TO_COMMIT", "REFERENCE_ONLY"}
    assert sum(entry["committed"] for entry in FORMS) == 17
    assert all(entry["license"] and entry["source_url"] and entry["revision"] for entry in FORMS)
    assert all(entry["classification"] == "SAFE_TO_COMMIT" for entry in FORMS if entry["committed"])
    assert all(not entry["committed"] for entry in FORMS if entry["classification"] == "REFERENCE_ONLY")


def test_committed_inventory_hashes_and_oracles_are_complete():
    declared = {entry["path"] for entry in FORMS if entry["committed"]}
    present = {
        path.relative_to(FIELD).as_posix()
        for path in (FIELD / "committed").rglob("*.xlsx")
    }
    assert declared == present
    for entry in FORMS:
        assert len(entry["sha256"]) == 64
        assert entry["constructs"]
        assert set(entry["expected_rule_counts"]) == set(entry["adjudication"])
        if entry["committed"]:
            path = FIELD / entry["path"]
            assert sha256(path.read_bytes()).hexdigest() == entry["sha256"]


def test_construct_coverage_is_field_diverse():
    covered = {item for entry in FORMS for item in entry["constructs"]}
    required = {
        "nested_groups", "nested_repeats", "repeat_contained_selects",
        "choice_filter", "cascading_selects", "choice_auxiliary_columns",
        "large_choice_sheet", "multilingual_labels", "multilingual_hints",
        "multilingual_constraint_messages", "complex_relevance", "complex_constraints",
        "calculations", "defaults", "notes", "metadata_rows", "appearance",
        "parameters", "media_columns", "required_expressions", "read_only_expressions",
        "pulldata", "long_expressions", "large_production_form",
    }
    assert required <= covered


def test_committed_field_harness_replays_all_oracles_and_adjudicates_every_finding():
    report = validate()
    assert report["forms_executed"] == 17
    assert report["diagnostics"] == 41
    assert report["rule_counts"] == {
        "I18N001": 37, "LBL001": 1, "PX004": 1, "PX999": 1, "UX001": 1
    }
    assert sum(report["adjudication_counts"].values()) == report["diagnostics"]
    assert report["adjudication_counts"] == {
        "CONFIRMED_TRUE_POSITIVE": 39,
        "EXPECTED_PYXFORM": 1,
        "PX999_EXPLAINED": 1,
    }
