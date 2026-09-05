from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from xlsform_lint.config import ConfigSettings, NATIVE_RULE_IDS, PX_RULE_IDS
from xlsform_lint.diagnostics import Diagnostic, DiagnosticOrigin, Severity
from xlsform_lint.policy import (
    CliPolicyOptions,
    apply_policy,
    exit_code_for_policy,
    expand_selectors,
    resolve_policy,
)


def _diagnostic(rule_id: str, severity: Severity, origin: DiagnosticOrigin) -> Diagnostic:
    return Diagnostic(rule_id, severity, f"finding for {rule_id}", None, origin)


def test_profiles_are_minimal_and_px_is_always_error_metadata() -> None:
    default = resolve_policy(ConfigSettings(), CliPolicyOptions())
    strict = resolve_policy(ConfigSettings(), CliPolicyOptions(profile="strict"))
    assert default.fail_on is strict.fail_on is Severity.ERROR
    assert default.native_severities["UX002"] is Severity.INFO
    assert strict.native_severities["UX002"] is Severity.WARNING
    assert {key: value for key, value in default.native_severities.items() if key != "UX002"} == {
        key: value for key, value in strict.native_severities.items() if key != "UX002"
    }
    assert PX_RULE_IDS <= default.enabled_rule_ids


@pytest.mark.parametrize(
    ("configured", "expected"),
    [("error", Severity.ERROR), ("warning", Severity.WARNING), ("info", Severity.INFO), ("off", None)],
)
def test_every_native_policy_state_resolves(configured: str, expected: Severity | None) -> None:
    policy = resolve_policy(ConfigSettings(rule_overrides=(("UX001", configured),)), CliPolicyOptions())
    assert policy.native_severities["UX001"] is expected
    assert set(policy.native_severities) == NATIVE_RULE_IDS
    with pytest.raises(TypeError):
        policy.native_severities["UX001"] = Severity.INFO  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        policy.fail_on = Severity.INFO  # type: ignore[misc]


def test_severity_application_replaces_frozen_diagnostic_without_other_changes() -> None:
    original = _diagnostic("UX001", Severity.WARNING, DiagnosticOrigin.NATIVE)
    policy = resolve_policy(ConfigSettings(rule_overrides=(("UX001", "error"),)), CliPolicyOptions())
    result = apply_policy((original,), policy)
    assert result[0] is not original
    assert result[0].severity is Severity.ERROR
    assert original.severity is Severity.WARNING
    assert result[0].rule_id == original.rule_id
    assert result[0].origin == original.origin
    assert result[0].message == original.message
    assert result[0].source == original.source
    assert result[0].related == original.related
    assert result[0].help == original.help


def test_selector_expansion_order_and_include_then_ignore() -> None:
    assert expand_selectors(("PX005", "CHO001")) == ("CHO001", "PX005")
    assert expand_selectors(("I18N", "LBL")) == ("I18N001", "LBL001", "LBL002")
    policy = resolve_policy(
        ConfigSettings(include=("UX",), ignore=("UX002",)), CliPolicyOptions()
    )
    assert policy.enabled_rule_ids == frozenset({"UX001"})


def test_cli_selection_fields_replace_config_fields_independently() -> None:
    config = ConfigSettings(include=("UX",), ignore=("UX002",))
    assert resolve_policy(config, CliPolicyOptions(include=("LBL",))).enabled_rule_ids == frozenset(
        {"LBL001", "LBL002"}
    )
    assert resolve_policy(config, CliPolicyOptions(ignore=("UX001",))).enabled_rule_ids == frozenset(
        {"UX002"}
    )


def test_profile_config_and_cli_precedence() -> None:
    config = ConfigSettings(
        profile="default", fail_on="warning", rule_overrides=(("UX002", "info"),)
    )
    policy = resolve_policy(config, CliPolicyOptions(profile="strict", fail_on="error"))
    assert policy.profile == "strict"
    assert policy.native_severities["UX002"] is Severity.INFO
    assert policy.fail_on is Severity.ERROR


@pytest.mark.parametrize(
    ("threshold", "severity", "expected"),
    [
        ("error", Severity.ERROR, 1), ("error", Severity.WARNING, 0), ("error", Severity.INFO, 0),
        ("warning", Severity.ERROR, 1), ("warning", Severity.WARNING, 1), ("warning", Severity.INFO, 0),
        ("info", Severity.ERROR, 1), ("info", Severity.WARNING, 1), ("info", Severity.INFO, 1),
    ],
)
def test_fail_threshold_matrix(threshold: str, severity: Severity, expected: int) -> None:
    diagnostic = _diagnostic("UX001", severity, DiagnosticOrigin.NATIVE)
    policy = resolve_policy(ConfigSettings(), CliPolicyOptions(fail_on=threshold))
    assert exit_code_for_policy((diagnostic,), (diagnostic,), policy) == expected


def test_off_and_ignore_win_over_severity_and_hidden_px_still_fails() -> None:
    native = _diagnostic("UX001", Severity.WARNING, DiagnosticOrigin.NATIVE)
    px = _diagnostic("PX005", Severity.ERROR, DiagnosticOrigin.PYXFORM)
    policy = resolve_policy(
        ConfigSettings(rule_overrides=(("UX001", "error"),)),
        CliPolicyOptions(ignore=("UX001", "PX005")),
    )
    visible = apply_policy((native, px), policy)
    assert visible == ()
    assert exit_code_for_policy((native, px), visible, policy) == 1
