"""Minimal command-line interface for the Phase 1 diagnostic kernel."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from .diagnostics import exit_code_for
from .engine import InputError, lint_workbook
from .text_formatter import format_diagnostics


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="xlsform-lint")
    parser.add_argument("workbook", help="path to one XLSForm .xlsx workbook")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Render lint results and map expected and unexpected failures to exit codes."""

    args = build_parser().parse_args(argv)
    try:
        diagnostics = lint_workbook(args.workbook)
    except InputError as error:
        print(f"xlsform-lint: error: {error}", file=sys.stderr)
        return 2
    except Exception:
        print("xlsform-lint: internal error", file=sys.stderr)
        return 3

    sys.stdout.write(format_diagnostics(diagnostics))
    return exit_code_for(diagnostics)
