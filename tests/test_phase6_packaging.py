from __future__ import annotations

import email
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_packaging_contract_and_version_boundary() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    project = data["project"]

    assert data["build-system"]["build-backend"] == "setuptools.build_meta"
    assert project["name"] == "xlsform-lint"
    assert project["version"] == "0.1.1"
    assert project["description"] == (
        "A Ruff/ESLint-style linter for XLSForm, built on pyxform."
    )
    assert project["readme"] == "README.md"
    assert (ROOT / project["readme"]).read_text().strip()
    assert project["license"] == "Apache-2.0"
    assert project["requires-python"] == ">=3.11"
    assert project["dependencies"] == ["pyxform>=4.5,<4.6", "openpyxl==3.1.5"]
    assert project["scripts"] == {"xlsform-lint": "xlsform_lint.cli:main"}
    assert project["urls"] == {
        "Repository": "https://github.com/imshahinul/xlsform-lint",
        "Issues": "https://github.com/imshahinul/xlsform-lint/issues",
    }


def test_built_wheel_contains_long_description_metadata(tmp_path: Path) -> None:
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(tmp_path)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    wheel = next(tmp_path.glob("xlsform_lint-0.1.1-*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        metadata_name = next(
            name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
        )
        metadata = email.message_from_bytes(archive.read(metadata_name))

    assert metadata["Version"] == "0.1.1"
    assert metadata["Summary"] == (
        "A Ruff/ESLint-style linter for XLSForm, built on pyxform."
    )
    assert metadata["Description-Content-Type"] == "text/markdown"
    assert metadata.get_payload().strip()


def test_runtime_does_not_depend_on_repository_schema() -> None:
    production = "\n".join(
        path.read_text() for path in sorted((ROOT / "src" / "xlsform_lint").glob("*.py"))
    )

    assert "xlsform-lint-output-v1.schema.json" not in production
    assert "schemas/" not in production
