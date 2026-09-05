from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


def _run(path: Path, *options: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "xlsform_lint", str(path), *(str(option) for option in options)],
        check=False,
        capture_output=True,
        text=True,
    )


@pytest.fixture
def policy_form(tmp_path: Path, xlsform_factory) -> Path:
    path = tmp_path / "project" / "forms" / "policy.xlsx"
    path.parent.mkdir(parents=True)
    return xlsform_factory(
        path,
        [
            ("type", "name", "label", "constraint", "required", "default"),
            ("text", "q", "Question", ". != ''", "yes", "value"),
        ],
    )


def test_default_profile_is_phase3_compatible_and_explicit_default_matches(policy_form: Path) -> None:
    implicit = _run(policy_form)
    explicit = _run(policy_form, "--profile", "default")
    assert (implicit.returncode, implicit.stdout, implicit.stderr) == (
        explicit.returncode, explicit.stdout, explicit.stderr
    )
    assert implicit.returncode == 0
    assert "UX001 warning" in implicit.stdout
    assert "UX002 info" in implicit.stdout
    assert implicit.stdout.endswith("0 errors, 1 warning, 1 info\n")
    assert implicit.stderr == ""


def test_strict_profile_only_promotes_ux002(policy_form: Path) -> None:
    result = _run(policy_form, "--profile", "strict")
    assert result.returncode == 0
    assert "UX001 warning" in result.stdout
    assert "UX002 warning" in result.stdout
    assert result.stdout.endswith("0 errors, 2 warnings\n")


def test_config_selected_strict_and_config_rule_override_precedence(policy_form: Path) -> None:
    strict = policy_form.parent / "strict.toml"
    strict.write_text('profile = "strict"\n', encoding="utf-8")
    strict_result = _run(policy_form, "--config", strict)
    assert "UX001 warning" in strict_result.stdout
    assert "UX002 warning" in strict_result.stdout

    overridden = policy_form.parent / "overridden.toml"
    overridden.write_text('profile = "strict"\n[rules]\nUX002 = "info"\n', encoding="utf-8")
    override_result = _run(policy_form, "--config", overridden)
    assert "UX002 info" in override_result.stdout
    assert "UX002 warning" not in override_result.stdout


@pytest.mark.parametrize(
    ("severity", "threshold", "expected_exit", "rendered"),
    [
        ("error", "error", 1, "UX001 error"),
        ("info", "warning", 0, "UX001 info"),
        ("off", "info", 1, None),
    ],
)
def test_native_severity_override_and_threshold_integration(
    policy_form: Path,
    severity: str,
    threshold: str,
    expected_exit: int,
    rendered: str | None,
) -> None:
    config = policy_form.parent / "severity.toml"
    config.write_text(f'[rules]\nUX001 = "{severity}"\n', encoding="utf-8")
    result = _run(policy_form, "--config", config, "--fail-on", threshold)
    assert result.returncode == expected_exit
    assert ("UX001" in result.stdout) is (rendered is not None)
    if rendered is not None:
        assert rendered in result.stdout


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        ((), 0),
        (("--fail-on", "warning"), 1),
        (("--fail-on", "info"), 1),
        (("--select", "UX002", "--fail-on", "warning"), 0),
        (("--select", "UX002", "--fail-on", "info"), 1),
    ],
)
def test_fail_threshold_cli_matrix(policy_form: Path, options: tuple[str, ...], expected: int) -> None:
    assert _run(policy_form, *options).returncode == expected


def test_auto_discovery_parent_nearest_and_unrelated_sibling(policy_form: Path) -> None:
    project = policy_form.parents[1]
    parent_config = project / ".xlsform-lint.toml"
    parent_config.write_text('[rules]\nUX001 = "error"\n', encoding="utf-8")
    sibling = project.parent / "other-project"
    sibling.mkdir()
    (sibling / ".xlsform-lint.toml").write_text('[rules]\nUX001 = "off"\n', encoding="utf-8")
    parent_result = _run(policy_form)
    assert parent_result.returncode == 1
    assert "UX001 error" in parent_result.stdout

    nearest = policy_form.parent / ".xlsform-lint.toml"
    nearest.write_text('[rules]\nUX001 = "info"\n', encoding="utf-8")
    nearest_result = _run(policy_form)
    assert nearest_result.returncode == 0
    assert "UX001 info" in nearest_result.stdout


def test_explicit_config_bypasses_discovery_but_cli_threshold_overrides(policy_form: Path) -> None:
    discovered = policy_form.parent / ".xlsform-lint.toml"
    discovered.write_text('[rules]\nUX001 = "off"\n', encoding="utf-8")
    explicit = policy_form.parent / "explicit.toml"
    explicit.write_text('[lint]\nfail_on = "warning"\n[rules]\nUX001 = "error"\n', encoding="utf-8")
    result = _run(policy_form, "--config", explicit, "--fail-on", "error")
    assert result.returncode == 1
    assert "UX001 error" in result.stdout
    assert "UX002 info" in result.stdout


def test_profile_config_and_cli_combined_precedence(policy_form: Path) -> None:
    config = policy_form.parent / "combined.toml"
    config.write_text(
        'profile = "default"\n[lint]\nfail_on = "warning"\n[rules]\nUX002 = "info"\n'
        '[select]\ninclude = ["UX"]\nignore = ["UX001"]\n',
        encoding="utf-8",
    )
    result = _run(
        policy_form,
        "--config", config,
        "--profile", "strict",
        "--select", "UX",
        "--ignore", "UX002",
        "--fail-on", "error",
    )
    assert result.returncode == 0
    assert "UX001 warning" in result.stdout
    assert "UX002" not in result.stdout
    assert result.stdout.endswith("0 errors, 1 warning\n")


def test_selection_and_off_interactions(policy_form: Path) -> None:
    config = policy_form.parent / "off.toml"
    config.write_text('[rules]\nUX001 = "off"\nUX002 = "warning"\n', encoding="utf-8")
    result = _run(policy_form, "--config", config, "--select", "UX", "--ignore", "UX002")
    assert result.returncode == 0
    assert result.stdout == "0 errors, 0 warnings\n"


@pytest.mark.parametrize(
    "options",
    [
        ("--config", "missing.toml"),
        ("--select", "UNKNOWN"),
        ("--select", "UX001,"),
        ("--ignore", "UX*"),
    ],
)
def test_cli_config_and_selector_errors_are_exit_2_without_traceback(
    policy_form: Path, options: tuple[str, ...]
) -> None:
    result = _run(policy_form, *options)
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.startswith("xlsform-lint: error:")
    assert "Traceback" not in result.stderr


def test_malformed_discovered_config_is_exit_2(policy_form: Path) -> None:
    (policy_form.parent / ".xlsform-lint.toml").write_text("[rules\n", encoding="utf-8")
    result = _run(policy_form)
    assert result.returncode == 2
    assert "unable to load configuration" in result.stderr
    assert "Traceback" not in result.stderr


def test_px_reporting_may_be_hidden_but_semantic_failure_remains(
    tmp_path: Path, xlsform_factory
) -> None:
    path = xlsform_factory(
        tmp_path / "invalid.xlsx",
        [("type", "name", "label", "constraint"), ("text", "1bad", "Bad", ". != ''")],
    )
    normal = _run(path)
    assert normal.returncode == 1
    assert "PX002 error" in normal.stdout and "UX001 warning" in normal.stdout

    hidden = _run(path, "--ignore", "PX")
    assert hidden.returncode == 1
    assert "PX002" not in hidden.stdout and "UX001 warning" in hidden.stdout

    selected_away = _run(path, "--select", "UX001")
    assert selected_away.returncode == 1
    assert "PX002" not in selected_away.stdout and "UX001 warning" in selected_away.stdout


def test_px_error_fails_at_every_threshold(tmp_path: Path, xlsform_factory) -> None:
    path = xlsform_factory(tmp_path / "px.xlsx", [("type", "name", "label"), ("text", "1bad", "Bad")])
    for threshold in ("error", "warning", "info"):
        assert _run(path, "--fail-on", threshold).returncode == 1


@pytest.mark.parametrize(
    "options",
    [
        (),
        ("--profile", "strict"),
        ("--select", "UX"),
        ("--ignore", "UX002"),
        ("--fail-on", "warning"),
        ("--profile", "strict", "--select", "UX", "--ignore", "UX001", "--fail-on", "warning"),
    ],
)
def test_repeated_cli_policy_runs_are_byte_identical(policy_form: Path, options: tuple[str, ...]) -> None:
    first = _run(policy_form, *options)
    second = _run(policy_form, *options)
    assert (first.returncode, first.stdout, first.stderr) == (second.returncode, second.stdout, second.stderr)


def test_discovery_does_not_add_an_xlsx_read(monkeypatch, policy_form: Path) -> None:
    import xlsform_lint.engine as engine
    from xlsform_lint.cli import main

    (policy_form.parent / ".xlsform-lint.toml").write_text('profile = "strict"\n', encoding="utf-8")
    reads = 0
    original = engine.read_workbook_bytes

    def counting_read(path):
        nonlocal reads
        reads += 1
        return original(path)

    monkeypatch.setattr(engine, "read_workbook_bytes", counting_read)
    assert main([str(policy_form)]) == 0
    assert reads == 1
