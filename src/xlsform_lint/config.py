"""Deterministic Phase 4 TOML discovery, loading, and validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


CONFIG_FILENAME = ".xlsform-lint.toml"
PROFILE_NAMES = frozenset({"default", "strict"})
FAIL_ON_VALUES = frozenset({"error", "warning", "info"})
FORMAT_VALUES = frozenset({"text", "json", "sarif"})
NATIVE_SEVERITY_VALUES = frozenset({"error", "warning", "info", "off"})
SELECTOR_PREFIXES = frozenset({"PX", "CHO", "LBL", "I18N", "UX", "ORD"})


@dataclass(frozen=True)
class RuleMetadata:
    """Policy-only metadata; semantic implementations remain elsewhere."""

    default_severity: str
    origin: str
    severity_configurable: bool


RULE_CATALOG = {
    **{
        rule_id: RuleMetadata("error", "pyxform", False)
        for rule_id in ("PX001", "PX002", "PX003", "PX004", "PX005", "PX006", "PX999")
    },
    **{
        rule_id: RuleMetadata("warning", "native", True)
        for rule_id in ("CHO001", "LBL001", "LBL002", "I18N001", "UX001", "ORD001")
    },
    "UX002": RuleMetadata("info", "native", True),
}
RULE_IDS = frozenset(RULE_CATALOG)
PX_RULE_IDS = frozenset(
    rule_id for rule_id, metadata in RULE_CATALOG.items() if metadata.origin == "pyxform"
)
NATIVE_RULE_IDS = RULE_IDS - PX_RULE_IDS


class ConfigError(Exception):
    """A predictable, user-facing configuration failure."""


@dataclass(frozen=True)
class ConfigSettings:
    """Validated explicit values from one configuration file."""

    profile: str | None = None
    fail_on: str | None = None
    rule_overrides: tuple[tuple[str, str], ...] = ()
    include: tuple[str, ...] | None = None
    ignore: tuple[str, ...] | None = None
    output_format: str | None = None
    path: Path | None = None


def discover_config(workbook: str | Path) -> Path | None:
    """Return the nearest config in the workbook parent's ancestry."""

    start = Path(workbook).expanduser().absolute().parent
    for directory in (start, *start.parents):
        candidate = directory / CONFIG_FILENAME
        if candidate.is_file():
            return candidate
    return None


def _expect_keys(table: dict[str, object], allowed: set[str], context: str) -> None:
    unknown = sorted(set(table) - allowed)
    if unknown:
        raise ConfigError(f"unknown {context} key: {unknown[0]}")


def _string(value: object, context: str, allowed: frozenset[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ConfigError(f"{context} must be one of: {choices}")
    return value


def validate_selectors(value: object, context: str) -> tuple[str, ...]:
    """Validate config selectors without accepting coercion or glob syntax."""

    if not isinstance(value, list):
        raise ConfigError(f"{context} must be a list of selectors")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise ConfigError(f"{context} items must be strings")
        selector = item.strip()
        if not selector:
            raise ConfigError(f"{context} contains an empty selector")
        if selector not in RULE_IDS and selector not in SELECTOR_PREFIXES:
            raise ConfigError(f"unknown selector in {context}: {selector}")
        result.append(selector)
    return tuple(result)


def parse_cli_selectors(value: str, option: str) -> tuple[str, ...]:
    """Parse a comma-separated CLI selector value."""

    tokens = value.split(",")
    if any(not token.strip() for token in tokens):
        raise ConfigError(f"{option} contains an empty selector")
    return validate_selectors([token.strip() for token in tokens], option)


def load_config(path: Path) -> ConfigSettings:
    """Load one TOML file and reject every unsupported field."""

    if not path.exists():
        raise ConfigError(f"configuration file does not exist: {path}")
    if not path.is_file():
        raise ConfigError(f"configuration path is not a file: {path}")
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise ConfigError(f"unable to load configuration {path}: {error}") from error

    _expect_keys(data, {"profile", "lint", "rules", "select"}, "top-level")
    profile = None
    if "profile" in data:
        profile = _string(data["profile"], "profile", PROFILE_NAMES)

    lint = data.get("lint", {})
    if not isinstance(lint, dict):
        raise ConfigError("lint must be a table")
    _expect_keys(lint, {"fail_on", "format"}, "lint")
    fail_on = None
    if "fail_on" in lint:
        fail_on = _string(lint["fail_on"], "lint.fail_on", FAIL_ON_VALUES)
    output_format = None
    if "format" in lint:
        output_format = _string(lint["format"], "lint.format", FORMAT_VALUES)

    rules = data.get("rules", {})
    if not isinstance(rules, dict):
        raise ConfigError("rules must be a table")
    overrides: list[tuple[str, str]] = []
    for rule_id in sorted(rules):
        if rule_id not in RULE_IDS:
            raise ConfigError(f"unknown rule ID: {rule_id}")
        if rule_id in PX_RULE_IDS:
            raise ConfigError(f"PX rule severity is fixed at error: {rule_id}")
        severity = _string(rules[rule_id], f"rules.{rule_id}", NATIVE_SEVERITY_VALUES)
        overrides.append((rule_id, severity))

    select = data.get("select", {})
    if not isinstance(select, dict):
        raise ConfigError("select must be a table")
    _expect_keys(select, {"include", "ignore"}, "select")
    include = validate_selectors(select["include"], "select.include") if "include" in select else None
    ignore = validate_selectors(select["ignore"], "select.ignore") if "ignore" in select else None
    return ConfigSettings(
        profile=profile,
        fail_on=fail_on,
        rule_overrides=tuple(overrides),
        include=include,
        ignore=ignore,
        output_format=output_format,
        path=path,
    )


def load_config_for(workbook: str | Path, explicit_path: str | Path | None) -> ConfigSettings:
    """Use an explicit config only, otherwise discover by input ancestry."""

    path = Path(explicit_path).expanduser() if explicit_path is not None else discover_config(workbook)
    return ConfigSettings() if path is None else load_config(path)
