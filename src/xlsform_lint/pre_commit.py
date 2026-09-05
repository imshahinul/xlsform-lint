"""Pre-commit adapter for the single-workbook command-line interface."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from .cli import main as cli_main


def main(argv: Sequence[str] | None = None) -> int:
    """Lint every filename and preserve the strongest CLI exit class."""

    filenames = tuple(sys.argv[1:] if argv is None else argv)
    strongest = 0
    for filename in filenames:
        result = cli_main((filename,))
        strongest = max(strongest, result)
    return strongest


if __name__ == "__main__":  # pragma: no cover - executable module boundary
    raise SystemExit(main())
