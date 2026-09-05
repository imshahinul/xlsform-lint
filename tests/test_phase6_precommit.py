from __future__ import annotations

from pathlib import Path

import pytest

from xlsform_lint import pre_commit


def test_hook_metadata_has_frozen_contract() -> None:
    metadata = (Path(__file__).parents[1] / ".pre-commit-hooks.yaml").read_text()

    assert "- id: xlsform-lint\n" in metadata
    assert "  name: xlsform-lint\n" in metadata
    assert "  entry: python -m xlsform_lint.pre_commit\n" in metadata
    assert "  language: python\n" in metadata
    assert "  files: \\.xlsx$\n" in metadata


@pytest.mark.parametrize(
    ("results", "expected"),
    [
        ((0, 0), 0),
        ((0, 1), 1),
        ((1, 2, 0), 2),
        ((2, 3, 1), 3),
    ],
)
def test_adapter_lints_each_file_and_preserves_strongest_exit(
    monkeypatch: pytest.MonkeyPatch, results: tuple[int, ...], expected: int
) -> None:
    calls: list[tuple[str, ...]] = []
    pending = iter(results)

    def fake_cli(argv: tuple[str, ...]) -> int:
        calls.append(argv)
        return next(pending)

    monkeypatch.setattr(pre_commit, "cli_main", fake_cli)
    filenames = tuple(f"form-{index}.xlsx" for index in range(len(results)))

    assert pre_commit.main(filenames) == expected
    assert calls == [(filename,) for filename in filenames]
