# Pre-commit integration

The repository publishes a Python hook with ID `xlsform-lint`. It selects files
whose names end in `.xlsx` and never modifies them. Each filename supplied by
pre-commit is linted once in the supplied order; the hook returns the strongest
exit class encountered (`3 > 2 > 1 > 0`).

Use the public repository and the released tag for this patch release:

```yaml
repos:
  - repo: https://github.com/imshahinul/xlsform-lint
    rev: v0.1.1
    hooks:
      - id: xlsform-lint
```

The hook uses the ordinary default threshold: errors fail, while warnings are
reported without failing. For every workbook, `.xlsform-lint.toml` discovery
starts in that workbook's directory and walks through its parents, so repository
policy applies in the same way as a direct `xlsform-lint FORM.xlsx` invocation.
