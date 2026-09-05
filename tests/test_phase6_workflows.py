from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_release_workflow_builds_and_smokes_without_publishing() -> None:
    workflow = (ROOT / ".github/workflows/release.yml").read_text()

    assert "python -m build" in workflow
    assert "dist/*.whl" in workflow
    assert "/bin/xlsform-lint" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "workflow_dispatch:" in workflow
    assert "pypa/gh-action-pypi-publish" not in workflow
    assert "twine upload" not in workflow
    assert "pip install -e" not in workflow


def test_documented_public_install_is_marked_as_future() -> None:
    readme = (ROOT / "README.md").read_text()
    actions = (ROOT / "docs/github-actions.md").read_text()

    assert "After the first public package release" in readme
    assert "After the first public package release" in actions
    assert "https://github.com/OWNER/xlsform-lint" in (
        ROOT / "docs/pre-commit.md"
    ).read_text()
