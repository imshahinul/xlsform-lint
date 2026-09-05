from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import pytest


GOLDEN = Path(__file__).parent / "golden"


def _make_case(root: Path, name: str, xlsform_factory) -> Path:
    cases = {
        "clean": [("type", "name", "label"), ("text", "q", "Question")],
        "mixed_native": [
            ("type", "name", "label", "constraint", "required", "default"),
            ("text", "q", "Français éclair", ". != ''", "yes", "value"),
        ],
        "px_error": [
            ("type", "name", "label", "constraint"),
            ("text", "1bad", "Bad", ". != ''"),
        ],
    }
    return xlsform_factory(
        root / f"{name}.xlsx",
        cases[name],
        settings_rows=(("form_title", "form_id", "version"), ("Golden", "golden", "1")),
    )


@pytest.mark.parametrize("name", ["clean", "mixed_native", "px_error"])
@pytest.mark.parametrize("output_format", ["text", "json", "sarif"])
def test_cli_output_is_byte_identical_to_committed_golden(
    tmp_path: Path, xlsform_factory, name: str, output_format: str
) -> None:
    path = _make_case(tmp_path, name, xlsform_factory)
    result = subprocess.run(
        [sys.executable, "-m", "xlsform_lint", path.name, "--format", output_format],
        cwd=tmp_path, check=False, capture_output=True,
    )
    assert result.returncode == (1 if name == "px_error" else 0)
    assert result.stderr == b""
    assert result.stdout == (GOLDEN / f"{name}.{output_format}").read_bytes()
    assert result.stdout.endswith(b"\n") and not result.stdout.endswith(b"\n\n")
