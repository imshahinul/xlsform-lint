from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path

import xlsform_lint
from xlsform_lint.cli import build_parser
from xlsform_lint.config import (
    FAIL_ON_VALUES,
    FORMAT_VALUES,
    PROFILE_NAMES,
    RULE_CATALOG,
    SELECTOR_PREFIXES,
)


ROOT = Path(__file__).parents[1]
RULE_IDS = {
    "PX001", "PX002", "PX003", "PX004", "PX005", "PX006", "PX999",
    "CHO001", "LBL001", "LBL002", "I18N001", "UX001", "ORD001", "UX002",
}


def test_apache_license_source_metadata_and_readme_agree() -> None:
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "Apache License\n                           Version 2.0, January 2004" in license_text
    assert "TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION" in license_text
    assert project["license"] == "Apache-2.0"
    assert project["license-files"] == ["LICENSE"]
    assert "[Apache License 2.0](LICENSE)" in readme
    assert not re.search(r"\b(MIT|BSD|GPL|LGPL|MPL)-?(?:2|3)?(?:\.0)?\b", readme)


def test_public_cli_surface_and_choices_are_frozen() -> None:
    parser = build_parser()
    actions = {option: action for action in parser._actions for option in action.option_strings}
    option_strings = {option for action in parser._actions for option in action.option_strings}
    positional = [action for action in parser._actions if not action.option_strings]

    assert parser.prog == "xlsform-lint"
    assert [action.dest for action in positional] == ["workbook"]
    assert option_strings == {
        "-h", "--help", "--config", "--select", "--ignore", "--profile", "--fail-on", "--format"
    }
    assert tuple(actions["--format"].choices) == ("text", "json", "sarif")
    assert tuple(actions["--profile"].choices) == ("default", "strict")
    assert tuple(actions["--fail-on"].choices) == ("error", "warning", "info")
    assert FORMAT_VALUES == frozenset({"text", "json", "sarif"})
    assert PROFILE_NAMES == frozenset({"default", "strict"})
    assert FAIL_ON_VALUES == frozenset({"error", "warning", "info"})
    assert SELECTOR_PREFIXES == frozenset({"PX", "CHO", "LBL", "I18N", "UX", "ORD"})
    with __import__("pytest").raises(SystemExit) as missing:
        parser.parse_args([])
    assert missing.value.code == 2
    assert isinstance(parser, argparse.ArgumentParser)


def test_public_rule_ids_are_the_exact_v1_catalog() -> None:
    assert set(RULE_CATALOG) == RULE_IDS


def test_public_python_surface_is_cli_only() -> None:
    assert xlsform_lint.__version__ == "0.1.0"
    assert not hasattr(xlsform_lint, "__all__")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "The supported V1 public interface is the CLI." in readme
    assert "from xlsform_lint" not in readme


def test_documented_rule_ids_and_references_are_complete() -> None:
    rules = (ROOT / "docs" / "rules.md").read_text(encoding="utf-8")
    headings = set(re.findall(r"^### ([A-Z0-9]+\d{3}) —", rules, flags=re.MULTILINE))
    assert headings == RULE_IDS

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for target in (
        "LICENSE", "docs/configuration.md", "docs/rules.md", "docs/installation.md",
        "docs/pre-commit.md", "docs/github-actions.md", "schemas/xlsform-lint-output-v1.schema.json",
        "xlsform-lint-v1-blueprint.md",
    ):
        assert f"]({target})" in readme


def test_release_workflow_is_manual_build_only_and_non_publishing() -> None:
    workflow = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    lowered = workflow.casefold()
    assert "workflow_dispatch:" in workflow
    assert "python -m pytest -q" in workflow
    assert "python -m build" in workflow
    assert "pip install dist/*.whl" in workflow
    assert "actions/upload-artifact@" in workflow
    assert "pypi" not in lowered and "testpypi" not in lowered
    assert "git tag" not in lowered
    assert "secrets." not in lowered


def test_runtime_has_no_forbidden_execution_or_mutation_boundaries() -> None:
    production = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((ROOT / "src" / "xlsform_lint").glob("*.py"))
    )
    forbidden = (
        "import requests", "import httpx", "import aiohttp", "urllib.request", "import socket",
        "subprocess", "shell=true", ".save(", "java", "external csv", "autofix",
    )
    assert all(token not in production.casefold() for token in forbidden)
