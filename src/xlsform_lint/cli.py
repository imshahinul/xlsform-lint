"""Stable command-line interface with the Phase 4 policy layer."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from .config import ConfigError, load_config_for, parse_cli_selectors
from .engine import InputError, lint_workbook
from .json_formatter import format_json
from .policy import CliPolicyOptions, apply_policy, exit_code_for_policy, resolve_policy
from .sarif_formatter import format_sarif
from .text_formatter import format_diagnostics


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xlsform-lint")
    parser.add_argument("workbook", help="path to one XLSForm .xlsx workbook")
    parser.add_argument("--config", metavar="PATH", help="use this configuration file only")
    parser.add_argument("--select", metavar="RULES", help="report only comma-separated rule IDs or prefixes")
    parser.add_argument("--ignore", metavar="RULES", help="hide comma-separated rule IDs or prefixes")
    parser.add_argument("--profile", choices=("default", "strict"), help="select a built-in policy profile")
    parser.add_argument("--fail-on", choices=("error", "warning", "info"), help="minimum failing severity")
    parser.add_argument("--format", choices=("text", "json", "sarif"), help="output format")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Render lint results and map expected and unexpected failures to exit codes."""

    args = build_parser().parse_args(argv)
    try:
        config = load_config_for(args.workbook, args.config)
        cli = CliPolicyOptions(
            profile=args.profile,
            fail_on=args.fail_on,
            include=parse_cli_selectors(args.select, "--select") if args.select is not None else None,
            ignore=parse_cli_selectors(args.ignore, "--ignore") if args.ignore is not None else None,
            output_format=args.format,
        )
        policy = resolve_policy(config, cli)
        raw_diagnostics = lint_workbook(args.workbook)
        diagnostics = apply_policy(raw_diagnostics, policy)
    except (ConfigError, InputError) as error:
        print(f"xlsform-lint: error: {error}", file=sys.stderr)
        return 2
    except Exception:
        print("xlsform-lint: internal error", file=sys.stderr)
        return 3

    try:
        formatters = {
            "text": lambda: format_diagnostics(diagnostics),
            "json": lambda: format_json(args.workbook, diagnostics),
            "sarif": lambda: format_sarif(args.workbook, diagnostics),
        }
        rendered = formatters[policy.output_format]()
        exit_code = exit_code_for_policy(raw_diagnostics, diagnostics, policy)
        sys.stdout.write(rendered)
    except Exception:
        print("xlsform-lint: internal error", file=sys.stderr)
        return 3
    return exit_code
