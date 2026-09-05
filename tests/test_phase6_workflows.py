from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_release_workflow_uses_manual_trusted_publishing() -> None:
    workflow = (ROOT / ".github/workflows/release.yml").read_text()

    assert workflow.count("python -m build") == 1
    assert "dist/*.whl" in workflow
    assert "/bin/xlsform-lint" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "actions/download-artifact@v4" in workflow
    assert "workflow_dispatch:" in workflow
    assert "environment:\n      name: pypi" in workflow
    assert "id-token: write" in workflow
    assert "pypa/gh-action-pypi-publish@release/v1" in workflow
    assert "packages-dir: dist/" in workflow
    assert "twine upload" not in workflow
    assert "password:" not in workflow
    assert "username:" not in workflow
    assert "PYPI_TOKEN" not in workflow
    assert "TWINE_PASSWORD" not in workflow
    assert "test.pypi.org" not in workflow
    assert "gh release" not in workflow
    assert "git tag" not in workflow
    assert "pip install -e" not in workflow


def test_documented_public_install_is_marked_as_future() -> None:
    readme = (ROOT / "README.md").read_text()
    actions = (ROOT / "docs/github-actions.md").read_text()

    assert "After the first public package release" in readme
    assert "After the first public package release" in actions
    assert "https://github.com/imshahinul/xlsform-lint" in (
        ROOT / "docs/pre-commit.md"
    ).read_text()
