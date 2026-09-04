from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook


@pytest.fixture
def workbook_factory():
    def create(path: Path, *, question_type: str = "text") -> Path:
        workbook = Workbook()
        survey = workbook.active
        survey.title = "Survey"
        survey.append(("type", "name", "label"))
        survey.append((question_type, "person_name", "Person name"))
        settings = workbook.create_sheet("settings")
        settings.append(("form_title", "form_id", "version"))
        settings.append(("Kernel Proof", "kernel_proof", "1"))
        workbook.save(path)
        workbook.close()
        return path

    return create
