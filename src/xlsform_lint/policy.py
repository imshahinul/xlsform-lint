"""Centralized immutable Phase 4 policy resolution and application."""

from __future__ import annotations

from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Mapping

from .config import NATIVE_RULE_IDS, PX_RULE_IDS, RULE_CATALOG, RULE_IDS, ConfigSettings
from .diagnostics import Diagnostic, DiagnosticOrigin, Severity, sort_diagnostics


DEFAULT_NATIVE_SEVERITIES = MappingProxyType(
    {
        rule_id: Severity[metadata.default_severity.upper()]
        for rule_id, metadata in RULE_CATALOG.items()
        if rule_id in NATIVE_RULE_IDS
    }
)
PROFILE_OVERRIDES = MappingProxyType(
    {
        "default": MappingProxyType({}),
        "strict": MappingProxyType({"UX002": Severity.WARNING}),
    }
)
SEVERITY_BY_NAME = MappingProxyType(
    {"error": Severity.ERROR, "warning": Severity.WARNING, "info": Severity.INFO}
)


@dataclass(frozen=True)
class CliPolicyOptions:
    """Explicit policy options supplied on the command line."""

    profile: str | None = None
    fail_on: str | None = None
    include: tuple[str, ...] | None = None
    ignore: tuple[str, ...] | None = None


@dataclass(frozen=True)
class EffectivePolicy:
    """Fully resolved policy; mappings and sets are read-only values."""

    profile: str
    fail_on: Severity
    native_severities: Mapping[str, Severity | None]
    enabled_rule_ids: frozenset[str]


def expand_selectors(selectors: tuple[str, ...]) -> tuple[str, ...]:
    """Expand exact IDs and category prefixes in catalog order."""

    matched = {
        rule_id
        for selector in selectors
        for rule_id in RULE_IDS
        if rule_id == selector or rule_id.startswith(selector)
    }
    return tuple(sorted(matched))


def resolve_policy(config: ConfigSettings, cli: CliPolicyOptions) -> EffectivePolicy:
    """Resolve built-ins -> selected profile -> config -> explicit CLI.

    CLI profile selects the profile layer; config rule overrides still apply
    afterward. Explicit CLI include and ignore each replace that config field.
    Ignore wins over include. PX selection controls reporting only.
    """

    profile = cli.profile or config.profile or "default"
    native: dict[str, Severity | None] = dict(DEFAULT_NATIVE_SEVERITIES)
    native.update(PROFILE_OVERRIDES[profile])
    for rule_id, severity in config.rule_overrides:
        native[rule_id] = None if severity == "off" else SEVERITY_BY_NAME[severity]

    include = cli.include if cli.include is not None else config.include
    ignore = cli.ignore if cli.ignore is not None else config.ignore
    enabled = set(RULE_IDS if include is None else expand_selectors(include))
    if ignore is not None:
        enabled.difference_update(expand_selectors(ignore))

    fail_on = SEVERITY_BY_NAME[cli.fail_on or config.fail_on or "error"]
    return EffectivePolicy(
        profile=profile,
        fail_on=fail_on,
        native_severities=MappingProxyType(native),
        enabled_rule_ids=frozenset(enabled),
    )


def apply_policy(
    diagnostics: tuple[Diagnostic, ...], policy: EffectivePolicy
) -> tuple[Diagnostic, ...]:
    """Filter reporting and copy native diagnostics with effective severity."""

    effective: list[Diagnostic] = []
    for diagnostic in diagnostics:
        if diagnostic.rule_id not in policy.enabled_rule_ids:
            continue
        if diagnostic.origin is DiagnosticOrigin.NATIVE:
            severity = policy.native_severities[diagnostic.rule_id]
            if severity is None:
                continue
            diagnostic = replace(diagnostic, severity=severity)
        effective.append(diagnostic)
    return sort_diagnostics(effective)


def exit_code_for_policy(
    raw_diagnostics: tuple[Diagnostic, ...],
    visible_diagnostics: tuple[Diagnostic, ...],
    policy: EffectivePolicy,
) -> int:
    """Fail at threshold while preserving hidden PX semantic failures."""

    hidden_or_visible_px_error = any(
        item.rule_id in PX_RULE_IDS and item.severity is Severity.ERROR
        for item in raw_diagnostics
    )
    threshold_finding = any(item.severity >= policy.fail_on for item in visible_diagnostics)
    return int(hidden_or_visible_px_error or threshold_finding)
