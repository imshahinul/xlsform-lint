from __future__ import annotations

from pathlib import Path

import pytest

from xlsform_lint.config import (
    ConfigError,
    discover_config,
    load_config,
    load_config_for,
    parse_cli_selectors,
)


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_valid_minimal_and_full_configuration(tmp_path: Path) -> None:
    minimal = load_config(_write(tmp_path / "minimal.toml", ""))
    assert minimal.profile is minimal.fail_on is None
    assert minimal.rule_overrides == ()

    full = load_config(_write(tmp_path / "full.toml", """
profile = "strict"
[lint]
fail_on = "warning"
format = "text"
[rules]
UX001 = "error"
UX002 = "off"
I18N001 = "info"
[select]
include = ["PX", "CHO001", "LBL", "I18N", "UX", "ORD"]
ignore = ["UX002"]
"""))
    assert full.profile == "strict"
    assert full.fail_on == "warning"
    assert dict(full.rule_overrides) == {"I18N001": "info", "UX001": "error", "UX002": "off"}
    assert full.include == ("PX", "CHO001", "LBL", "I18N", "UX", "ORD")
    assert full.ignore == ("UX002",)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ('surprise = true', "unknown top-level key"),
        ('[lint]\nsurprise = true', "unknown lint key"),
        ('[select]\nsurprise = []', "unknown select key"),
        ('profile = "maximum"', "profile must be one of"),
        ('[lint]\nfail_on = "fatal"', "lint.fail_on must be one of"),
        ('[lint]\nformat = "yaml"', "lint.format must be one of"),
        ('[rules]\nUX999 = "warning"', "unknown rule ID"),
        ('[rules]\nUX001 = "fatal"', "rules.UX001 must be one of"),
        ('[rules]\nPX005 = "warning"', "PX rule severity is fixed"),
        ('[rules]\nPX005 = "off"', "PX rule severity is fixed"),
        ('[select]\ninclude = "UX"', "must be a list"),
        ('[select]\nignore = [1]', "items must be strings"),
        ('[select]\ninclude = ["UNKNOWN"]', "unknown selector"),
        ('[select]\nignore = ["  "]', "empty selector"),
        ('[rules]\nUX001 = [', "unable to load configuration"),
    ],
)
def test_invalid_configuration_is_rejected(tmp_path: Path, text: str, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        load_config(_write(tmp_path / "bad.toml", text))


def test_config_discovery_is_input_ancestry_only_and_nearest_wins(tmp_path: Path) -> None:
    project = tmp_path / "project"
    form = project / "forms" / "nested" / "form.xlsx"
    form.parent.mkdir(parents=True)
    parent = _write(project / ".xlsform-lint.toml", 'profile = "default"')
    sibling = _write(tmp_path / "other-project" / ".xlsform-lint.toml", 'profile = "strict"')
    assert sibling.exists()
    assert discover_config(form) == parent

    nearest = _write(project / "forms" / ".xlsform-lint.toml", 'profile = "strict"')
    assert discover_config(form) == nearest
    assert load_config_for(form, None).profile == "strict"


def test_no_config_and_explicit_config_authority(tmp_path: Path) -> None:
    form = tmp_path / "project" / "form.xlsx"
    form.parent.mkdir()
    discovered = _write(form.parent / ".xlsform-lint.toml", 'profile = "strict"')
    explicit = _write(tmp_path / "explicit.toml", 'profile = "default"')
    assert load_config_for(form, explicit).path == explicit
    discovered.unlink()
    assert load_config_for(form, None).path is None
    with pytest.raises(ConfigError, match="does not exist"):
        load_config_for(form, tmp_path / "missing.toml")
    with pytest.raises(ConfigError, match="not a file"):
        load_config_for(form, tmp_path)


@pytest.mark.parametrize("selector", ["PX005", "CHO001", "UX002", "PX", "CHO", "LBL", "I18N", "UX", "ORD"])
def test_cli_selector_grammar_accepts_exact_ids_and_prefixes(selector: str) -> None:
    assert parse_cli_selectors(selector, "--select") == (selector,)


@pytest.mark.parametrize("selector", ["UNKNOWN", "UX999", "UX*", "PX00?", "", "UX001,"])
def test_cli_selector_grammar_rejects_unknown_glob_and_blank(selector: str) -> None:
    with pytest.raises(ConfigError):
        parse_cli_selectors(selector, "--select")


def test_cli_selector_whitespace_is_normalized() -> None:
    assert parse_cli_selectors(" I18N , LBL ", "--select") == ("I18N", "LBL")
