# Phase 3.0B field-validation corpus

This corpus measures the frozen `xlsform-lint` 0.2.0 engine against 20
externally authored XLSForms from three independent source families. It is an
evidence corpus, not a source of new rule semantics.

The 17 committed workbooks are redistributed from repositories with explicit
BSD-2-Clause or MIT licenses. The three ODK sample workbooks are
`REFERENCE_ONLY`: their exact bytes are exercised outside this repository and
are identified by repository revision and SHA-256 in `manifest.json`.

Run the committed corpus offline:

```bash
python3 scripts/phase3_field_validate.py
```

To include the reference-only ODK files, clone the pinned source outside this
repository and provide its checkout root:

```bash
python3 scripts/phase3_field_validate.py --reference-root /path/to/sample-forms
```

The harness verifies every source hash, executes the public engine once per
workbook, checks the frozen expected rule counts, expands the adjudication
policy to every emitted diagnostic, and emits JSON. Runtime values are
observations only and are never test assertions.

## Sources and redistribution

| Family | Revision | Classification | License/evidence |
| --- | --- | --- | --- |
| XLSForm/pyxform | `26006d0830570ffa3caead24b0c9a470278af2cf` | `SAFE_TO_COMMIT` | BSD-2-Clause; upstream `LICENSE` |
| stats4sd/xlsform_examples | `e3ef51c35e07aa151420d7d6f549a403c3111dd8` | `SAFE_TO_COMMIT` | MIT; upstream `LICENSE` |
| getodk/sample-forms | `8faa86f61b44f21008123f3409c4ea3c11653bb7` | `REFERENCE_ONLY` | no repository license found; bytes are not committed |

No private forms, submissions, participant data, credentials, or private URLs
are included. The existing 13-fixture Phase 2 corpus remains unchanged and is
the control group.
