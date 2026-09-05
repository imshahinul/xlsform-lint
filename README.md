# xlsform-lint

`xlsform-lint` is a developer-oriented, Ruff/ESLint-style linter for XLSForm.
It combines pyxform validation with native diagnostics and supports text, JSON,
and SARIF output.

## Installation

The package has not yet been published. After the first public package release,
installation will use:

```bash
python -m pip install xlsform-lint
```

For a local checkout, install the package into a virtual environment:

```bash
python -m pip install .
```

Python 3.11 or newer is required. The current package supports pyxform 4.5.x
(`pyxform>=4.5,<4.6`) and pins openpyxl 3.1.5.

## Five-minute usage

Lint one workbook with the default policy (errors fail; warnings are reported):

```bash
xlsform-lint FORM.xlsx
```

Fail CI on warnings, or emit JSON for another tool:

```bash
xlsform-lint FORM.xlsx --fail-on warning
xlsform-lint FORM.xlsx --format json
```

Project policy can be stored in `.xlsform-lint.toml`; it is discovered from the
workbook directory through its parents. Use `--config PATH` to select one file
explicitly. The CLI also supports `--select`, `--ignore`, and `--profile`.

## Integrations

- [Pre-commit](docs/pre-commit.md)
- [GitHub Actions](docs/github-actions.md)
- [Installation details](docs/installation.md)

The canonical implementation contract is recorded in
[`xlsform-lint-v1-blueprint.md`](xlsform-lint-v1-blueprint.md).
