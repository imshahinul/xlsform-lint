# Installation

## Future public release

`xlsform-lint` is not published to PyPI yet. After publication, install it in a
Python 3.11-or-newer environment with:

```bash
python -m pip install xlsform-lint
xlsform-lint --help
```

## Local source and artifact installation

Contributors can install a checkout non-editably:

```bash
python -m pip install .
```

To test exactly what a user will receive, build and install the wheel:

```bash
python -m pip install '.[dev]'
python -m build
python -m venv /tmp/xlsform-lint-smoke
/tmp/xlsform-lint-smoke/bin/python -m pip install dist/*.whl
/tmp/xlsform-lint-smoke/bin/xlsform-lint FORM.xlsx
```

The wheel exposes only the `xlsform-lint` console command. Normal lint runs are
local and network-free. Installation may contact a package index to obtain the
declared dependencies: `pyxform>=4.5,<4.6` and `openpyxl==3.1.5`.

The package is licensed under the [Apache License 2.0](../LICENSE).

Configuration belongs in `.xlsform-lint.toml` beside a workbook or in a parent
directory. For example:

```toml
[lint]
fail_on = "warning"

[rules]
UX001 = "error"
```

See the [pre-commit guide](pre-commit.md) and
[GitHub Actions guide](github-actions.md) for automation examples.
