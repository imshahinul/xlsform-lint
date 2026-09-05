from __future__ import annotations

import tomllib
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_packaging_contract_and_version_boundary() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    project = data["project"]

    assert data["build-system"]["build-backend"] == "setuptools.build_meta"
    assert project["name"] == "xlsform-lint"
    assert project["version"] == "0.1.0"
    assert project["requires-python"] == ">=3.11"
    assert project["dependencies"] == ["pyxform>=4.5,<4.6", "openpyxl==3.1.5"]
    assert project["scripts"] == {"xlsform-lint": "xlsform_lint.cli:main"}


def test_runtime_does_not_depend_on_repository_schema() -> None:
    production = "\n".join(
        path.read_text() for path in sorted((ROOT / "src" / "xlsform_lint").glob("*.py"))
    )

    assert "xlsform-lint-output-v1.schema.json" not in production
    assert "schemas/" not in production
