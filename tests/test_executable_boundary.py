from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from typing import BinaryIO

import pytest
from openpyxl import Workbook
from pyxform.errors import PyXFormError

from xlsform_lint.pyxform_adapter import convert_workbook
from xlsform_lint.source_reader import read_sheet_names, read_source_cell
from xlsform_lint.workbook_input import read_workbook_bytes


FATAL_MESSAGE = "Unknown question type 'definitely_not_a_type'."


def _write_workbook(path: Path, *, question_type: str) -> None:
    workbook = Workbook()
    survey = workbook.active
    survey.title = "survey"
    survey.append(("type", "name", "label"))
    survey.append((question_type, "person_name", "Person name"))

    settings = workbook.create_sheet("settings")
    settings.append(("form_title", "form_id", "version"))
    settings.append(("Boundary Proof", "boundary_proof", "1"))
    workbook.save(path)
    workbook.close()


def _capture_proof(workbook_bytes: bytes) -> tuple[object, ...]:
    sheet_names = read_sheet_names(workbook_bytes)
    source_fact = ("survey", 2, 1, read_source_cell(workbook_bytes, "survey", 2, 1))
    try:
        convert_workbook(workbook_bytes)
    except PyXFormError as error:
        failure = (type(error).__module__, type(error).__name__, str(error))
    else:  # pragma: no cover - the fixture must remain deliberately invalid
        pytest.fail("the fatal pyxform fixture unexpectedly converted")
    return sheet_names, source_fact, failure


def test_original_xlsx_is_acquired_once(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source_path = tmp_path / "fatal.xlsx"
    _write_workbook(source_path, question_type="definitely_not_a_type")
    original_open = Path.open
    opens = 0

    def counting_open(path: Path, *args: object, **kwargs: object) -> BinaryIO:
        nonlocal opens
        if path == source_path:
            opens += 1
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", counting_open)
    workbook_bytes = read_workbook_bytes(source_path)
    _capture_proof(workbook_bytes)

    assert opens == 1


def test_independent_copies_feed_both_lanes(tmp_path: Path) -> None:
    source_path = tmp_path / "valid.xlsx"
    _write_workbook(source_path, question_type="text")
    workbook_bytes = read_workbook_bytes(source_path)

    assert read_source_cell(workbook_bytes, "survey", 2, 3) == "Person name"
    first_result = convert_workbook(workbook_bytes)
    assert "person_name" in first_result.xform
    assert read_source_cell(workbook_bytes, "survey", 2, 3) == "Person name"
    second_result = convert_workbook(workbook_bytes)
    assert second_result.xform == first_result.xform


def test_adapter_executes_supported_convert_with_validation_disabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    source_path = tmp_path / "valid.xlsx"
    _write_workbook(source_path, question_type="text")
    workbook_bytes = read_workbook_bytes(source_path)

    real_result = convert_workbook(workbook_bytes)
    assert "person_name" in real_result.xform

    calls: list[tuple[object, bool]] = []

    def recording_convert(xlsform: object, *, validate: bool) -> object:
        calls.append((xlsform, validate))
        return real_result

    monkeypatch.setattr("xlsform_lint.pyxform_adapter.convert", recording_convert)
    assert convert_workbook(workbook_bytes) is real_result
    assert len(calls) == 1
    stream, validate = calls[0]
    assert hasattr(stream, "read")
    assert stream.read() == workbook_bytes
    assert validate is False


def test_fatal_pyxform_failure_is_capturable(tmp_path: Path) -> None:
    source_path = tmp_path / "fatal.xlsx"
    _write_workbook(source_path, question_type="definitely_not_a_type")

    with pytest.raises(PyXFormError, match="^Unknown question type") as captured:
        convert_workbook(read_workbook_bytes(source_path))

    assert str(captured.value) == FATAL_MESSAGE


def test_source_information_coexists_with_fatal_failure(tmp_path: Path) -> None:
    source_path = tmp_path / "fatal.xlsx"
    _write_workbook(source_path, question_type="definitely_not_a_type")

    proof = _capture_proof(read_workbook_bytes(source_path))

    assert proof == (
        ("survey", "settings"),
        ("survey", 2, 1, "definitely_not_a_type"),
        ("pyxform.errors", "PyXFormError", FATAL_MESSAGE),
    )


def test_processing_does_not_mutate_original_workbook(tmp_path: Path) -> None:
    source_path = tmp_path / "fatal.xlsx"
    _write_workbook(source_path, question_type="definitely_not_a_type")
    workbook_bytes = read_workbook_bytes(source_path)
    before_file = hashlib.sha256(source_path.read_bytes()).hexdigest()
    before_bytes = hashlib.sha256(workbook_bytes).hexdigest()

    _capture_proof(workbook_bytes)

    assert hashlib.sha256(source_path.read_bytes()).hexdigest() == before_file
    assert hashlib.sha256(workbook_bytes).hexdigest() == before_bytes
    assert source_path.read_bytes() == workbook_bytes


def test_repeated_execution_has_identical_stable_results(tmp_path: Path) -> None:
    source_path = tmp_path / "fatal.xlsx"
    _write_workbook(source_path, question_type="definitely_not_a_type")
    workbook_bytes = read_workbook_bytes(source_path)

    run_1 = _capture_proof(workbook_bytes)
    run_2 = _capture_proof(workbook_bytes)

    assert run_1 == run_2
    assert run_1[2] == ("pyxform.errors", "PyXFormError", FATAL_MESSAGE)


def test_phase1a_production_modules_do_not_reference_private_pyxform_models() -> None:
    package = Path(__file__).parents[1] / "src" / "xlsform_lint"
    phase1a_modules = (
        package / "workbook_input.py",
        package / "source_reader.py",
        package / "pyxform_adapter.py",
    )

    for module in phase1a_modules:
        source = module.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(module))
        assert "_survey" not in source
        assert "_pyxform" not in source
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imported = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                assert all(not name.startswith("pyxform.") for name in imported) or all(
                    name == "pyxform.xls2xform" for name in imported
                )
