# xlsform-lint

`xlsform-lint` is a developer-oriented, Ruff/ESLint-style linter for XLSForm.
It combines pyxform semantic validation with seven narrow native diagnostics and
supports deterministic text, JSON v1, and SARIF output. pyxform is the semantic
authority: this tool makes selected upstream failures easier to act on and adds
bounded authoring checks; it does not replace pyxform or XLSForm testing on the
target data-collection platform.

The project is currently unpublished. It does not validate runtime XPath
behavior, execute a form, load or validate external CSV data, or claim to find
everything outside pyxform's validation.

## Installation

Python 3.11 or newer is required. The package supports pyxform 4.5.x
(`pyxform>=4.5,<4.6`) and pins openpyxl 3.1.5.

For a local checkout or a built wheel:

```bash
python -m pip install .
python -m pip install dist/xlsform_lint-0.0.0-py3-none-any.whl
```

After the first public package release, the following will be the public
installation syntax. It is **future syntax only**; the package is not currently
published on PyPI:

```bash
python -m pip install xlsform-lint
```

See [installation details](docs/installation.md).

## Usage and output

Lint one workbook. Errors fail by default; warnings and information are shown
but do not fail:

```bash
xlsform-lint FORM.xlsx
xlsform-lint FORM.xlsx --fail-on warning
xlsform-lint FORM.xlsx --format json
xlsform-lint FORM.xlsx --format sarif
```

Text is intended for people. JSON follows the tracked
[JSON v1 schema](schemas/xlsform-lint-output-v1.schema.json). SARIF provides an
interchange format, although XLSX cells do not map naturally to source-code line
annotations.

## Configuration and policy

Store policy in `.xlsform-lint.toml`. Discovery starts at the workbook's
directory and uses the nearest ancestor file; `--config PATH` selects one file
explicitly. Resolution order is built-ins, selected `default` or `strict`
profile, config, then explicit CLI settings.

```toml
profile = "strict"

[lint]
fail_on = "warning"
format = "text"

[rules]
UX001 = "error"

[select]
include = ["PX", "CHO", "LBL", "I18N", "UX", "ORD"]
ignore = ["UX002"]
```

`--select RULES` and `--ignore RULES` accept comma-separated exact IDs or the
prefixes `PX`, `CHO`, `LBL`, `I18N`, `UX`, and `ORD`. `--fail-on` accepts
`error`, `warning`, or `info`; `--profile` accepts `default` or `strict`.
See the complete [configuration reference](docs/configuration.md).

## Integrations and reference

- [Rule catalog](docs/rules.md)
- [Configuration reference](docs/configuration.md)
- [Pre-commit](docs/pre-commit.md)
- [GitHub Actions](docs/github-actions.md)
- [Installation details](docs/installation.md)

The supported V1 public interface is the CLI. Python implementation modules are
internal unless explicitly exported and documented. The frozen architecture is
recorded in [`xlsform-lint-v1-blueprint.md`](xlsform-lint-v1-blueprint.md).

## License

`xlsform-lint` is licensed under the [Apache License 2.0](LICENSE).
