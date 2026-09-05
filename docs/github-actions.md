# GitHub Actions

No dedicated GitHub Action is required. Use a supported Python and invoke the
installed console script. The package is not published yet, so a workflow in a
checkout can install the local package:

```yaml
- uses: actions/setup-python@v5
  with:
    python-version: "3.11"

- name: Install XLSForm Lint from this checkout
  run: python -m pip install .

- name: Lint XLSForms
  run: xlsform-lint forms/main.xlsx --fail-on warning
```

After the first public package release, replace the local install step with:

```yaml
- name: Install XLSForm Lint
  run: python -m pip install xlsform-lint
```

Text output is the default. Machine-readable results can be retained as job
artifacts or consumed by later steps:

```yaml
- name: Write JSON results
  run: xlsform-lint forms/main.xlsx --format json > xlsform-lint.json

- name: Write SARIF results
  run: xlsform-lint forms/main.xlsx --format sarif > xlsform-lint.sarif
```

SARIF is useful for interoperable storage, but spreadsheet cell locations do
not map to GitHub's source-line annotations as naturally as text source files.
The repository's release workflow builds and locally verifies artifacts; it
does not publish to PyPI.
