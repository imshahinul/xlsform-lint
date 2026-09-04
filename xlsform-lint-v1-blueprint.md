# XLSForm Lint — V1 Blueprint and Scope Freeze

**Working project name:** `xlsform-lint`  
**Positioning:** *Ruff for XLSForm*  
**Primary interface:** `xlsform-lint path/to/form.xlsx`  
**Status:** V1 scope + architecture frozen; ready for implementation  
**Audience:** XLSForm authors, ODK/KoboToolbox developers, research/data-collection teams, CI maintainers, and tool builders

---

## Architecture freeze record

**Frozen:** 2026-09-04  
**Change control:** The V1 architecture below is implementation-authoritative. Do not reopen, reinterpret, or broaden it during Phase 1+ unless an executable blocker proves that a frozen assumption is invalid. Any required architecture change must be isolated, evidenced, and explicitly approved before adoption.

Frozen architectural decisions:

- Positioning remains **“Ruff/ESLint for XLSForm”**: `pyxform` is the semantic backend, not a competitor to reimplement.
- Read the XLSX input bytes once, then feed independent copies to two parallel lanes: (1) an `openpyxl` source/native-lint lane and (2) a pyxform semantic-validation lane.
- Do **not** derive the public lint model from pyxform private/internal representations such as `_pyxform` or `_survey`.
- Use `pyxform.xls2xform.convert(..., validate=False)` as the supported semantic boundary for V1.
- Native rules may continue when pyxform fails, but only when their declared prerequisites can be evaluated safely.
- Fatal pyxform validation is treated as **fail-fast in V1**: report all safely computable native diagnostics plus the first fatal pyxform semantic diagnostic. Do not monkey-patch pyxform, repeatedly mutate/re-run forms, or recreate its validators merely to aggregate upstream failures.
- Normalize supported pyxform failures through an isolated, version-scoped adapter into stable `PX*` IDs; use `PX999` as the conservative fallback for unrecognized upstream failures.
- Source mapping must preserve real workbook sheet names plus canonical identities and must emit only safely known precision (`exact`, `row`, `sheet`, or `file` confidence). Never fabricate cell precision.
- `PX001` is frozen as **`duplicate-name-in-scope`**. Scope-aware duplicate validity is delegated to pyxform. A naïve workbook-global duplicate-name check is prohibited. Related prior-definition locations may be shown only when unambiguous.
- Initial compatibility window: **Python >=3.11**, **pyxform >=4.5,<4.6**, **openpyxl==3.1.5**. Widening these ranges is a deliberate compatibility checkpoint, not an incidental dependency update.
- V1 boundaries remain: no autofix, no external CSV analysis, no runtime XPath correctness testing, no broad repeat-scope analysis, and no Java/network dependency for normal lint execution.

---

## 1. Product thesis

`xlsform-lint` is a deterministic static-analysis and developer-tooling layer for XLSForm.

It does **not** attempt to replace `pyxform`, ODK Validate, KoboToolbox validation, or runtime form testing. Instead, it builds on `pyxform` as the semantic authority for core XLSForm validity and adds a stable linting contract around it:

- stable rule IDs;
- normalized diagnostics;
- source-aware row/cell locations;
- error/warning/info severities;
- configurable rules and severity overrides;
- deterministic exit codes;
- human-readable and machine-readable output;
- pre-commit and CI integration;
- maintainability, translation, UX, and authoring-quality checks that are valid-form-but-suspicious rather than hard schema failures.

The project should benefit when `pyxform` improves. New upstream validation can be normalized into the linter rather than reimplemented independently.

### Core positioning statement

> **`xlsform-lint` is the developer linter for XLSForm: deterministic diagnostics, stable rules, configuration, CI, and quality checks on top of pyxform.**

### Mental model

```text
pyxform answers:      "Can this XLSForm be interpreted/converted correctly?"

xlsform-lint adds:    "Is this form structurally clean, maintainable,
                       well-localized, and safe to ship through a
                       modern development workflow?"
```

---

## 2. V1 goals

V1 must deliver a small but dependable CLI that can be adopted in a real repository from day one.

### 2.1 Functional goals

1. Accept a local `.xlsx` XLSForm as input.
2. Run canonical `pyxform` validation relevant to the form.
3. Normalize supported `pyxform` failures into stable `xlsform-lint` diagnostic IDs.
4. Build a source map from logical XLSForm elements back to workbook sheet/row/column/cell locations.
5. Run the frozen native V1 lint rules.
6. Emit diagnostics in:
   - text;
   - JSON;
   - SARIF.
7. Support deterministic exit codes suitable for shell scripts, CI, and pre-commit.
8. Support project-level configuration through `.xlsform-lint.toml`.
9. Support rule selection and suppression from the CLI.
10. Ship a documented pre-commit integration.
11. Ship a documented GitHub Actions integration.

### 2.2 Quality goals

V1 must be:

- deterministic;
- side-effect free;
- read-only with respect to the workbook;
- usable without Java;
- usable without network access;
- explicit about which diagnostics originate from pyxform versus native lint rules;
- conservative about warnings where XLSForm semantics permit legitimate exceptions;
- tested against representative ODK/Kobo-style forms.

---

## 3. Explicit V1 non-goals

The following are intentionally out of scope for V1.

### 3.1 No runtime logic execution

V1 does **not** execute XPath expressions or simulate form filling.

It does not determine whether a calculation, relevance condition, constraint, or choice filter is logically correct for all possible responses.

### 3.2 No behavioral form testing

V1 is not a replacement for an eventual scenario-testing product such as:

```text
xlsform-test
```

Behavioral assertions and enumerator-flow simulation belong in a separate future tool or project layer.

### 3.3 No external CSV/data-source validation

V1 does not inspect or resolve:

- `pulldata()` CSV files;
- `select_one_from_file` datasets;
- media attachments;
- external XML instances;
- server-side entities or remote datasets.

The parser may recognize those constructs sufficiently to avoid false-positive lint rules, but it does not validate the external resource itself.

### 3.4 No autofix

V1 never rewrites the workbook.

No `--fix` command.

No silent normalization.

No label insertion, renaming, or formula rewriting.

### 3.5 No broad repeat-scope engine

Repeat/reference scope analysis is deferred.

V1 must not attempt a partial repeat-scope implementation that could incorrectly flag valid forms.

### 3.6 No ordinary cross-group warning

References between ordinary groups are valid XLSForm patterns and are not intrinsically suspicious.

### 3.7 No full XPath semantic validator

V1 may statically identify `${field}` references when needed for source-aware rules, but it does not become an independent XPath parser/engine.

### 3.8 No GUI or hosted service

V1 is CLI-first.

A web interface, editor extension, hosted CI service, or SaaS layer may be evaluated later.

---

## 4. Architectural principles

### 4.1 Pyxform is the semantic backend

Do not independently reimplement XLSForm validity rules that `pyxform` already owns.

Where `pyxform` detects an error, `xlsform-lint` should:

1. capture or normalize the error;
2. assign a stable project rule ID;
3. attach the best source location available;
4. emit it through the standard diagnostic pipeline.

This avoids a long-term race with XLSForm semantics.

### 4.2 Workbook parsing is source-oriented

Use `openpyxl` or a thin workbook-reading layer to retain source fidelity:

- sheet name;
- row number;
- column heading;
- cell coordinate;
- raw cell value.

This is necessary because semantic error messages do not always preserve sufficient workbook location information for high-quality lint output.

### 4.3 Native rules run over a normalized model

Native rules should not each independently inspect raw spreadsheets.

Instead, construct a small internal lint model representing:

- survey rows;
- choice rows;
- settings;
- recognized language columns;
- select/list relationships;
- field order;
- selected expression references required by V1 rules;
- source locations.

Rules consume that stable model.

### 4.4 Diagnostics are the product contract

The core long-term API is not a particular parser implementation. It is the diagnostic contract:

```text
rule_id
severity
message
source
location
origin
optional help
optional related locations
```

Stable diagnostics enable editor integrations, CI baselines, SARIF, and ecosystem tooling later.

---

## 5. High-level architecture

```text
                         XLSForm .xlsx
                              │
               ┌──────────────┴──────────────┐
               │                             │
               ▼                             ▼
        Workbook/source reader          pyxform adapter
        (openpyxl or equivalent)        canonical semantics
               │                             │
               ▼                             ▼
          source map                    upstream diagnostics
               │                             │
               └──────────────┬──────────────┘
                              ▼
                      normalized lint model
                              │
               ┌──────────────┴──────────────┐
               │                             │
               ▼                             ▼
        native lint rules             diagnostic normalizer
               │                             │
               └──────────────┬──────────────┘
                              ▼
                     diagnostic collection
                              │
             ┌────────────────┼─────────────────┐
             ▼                ▼                 ▼
           text              JSON              SARIF
             │                │                 │
             └────────────────┴─────────────────┘
                              ▼
                         exit status
```

---

## 6. Proposed Python package layout

The exact layout can evolve during implementation, but V1 should preserve clear boundaries.

```text
xlsform-lint/
├── pyproject.toml
├── README.md
├── LICENSE
├── CHANGELOG.md
├── src/
│   └── xlsform_lint/
│       ├── __init__.py
│       ├── __main__.py
│       ├── cli.py
│       ├── config.py
│       ├── diagnostics.py
│       ├── model.py
│       ├── source_map.py
│       ├── workbook.py
│       ├── pyxform_adapter.py
│       ├── engine.py
│       ├── rules/
│       │   ├── __init__.py
│       │   ├── registry.py
│       │   ├── labels.py
│       │   ├── translations.py
│       │   ├── choices.py
│       │   ├── constraints.py
│       │   ├── ordering.py
│       │   └── defaults.py
│       └── formatters/
│           ├── __init__.py
│           ├── text.py
│           ├── json.py
│           └── sarif.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── fixtures/
│   └── golden/
└── docs/
    ├── rules.md
    ├── configuration.md
    ├── pre-commit.md
    └── github-actions.md
```

---

## 7. Internal data model

V1 should define typed internal structures early instead of passing loose dictionaries between components.

Illustrative model:

```python
@dataclass(frozen=True)
class SourceLocation:
    path: str
    sheet: str
    row: int
    column: str | None
    cell: str | None


@dataclass(frozen=True)
class SurveyRow:
    index: int
    type: str | None
    name: str | None
    values: Mapping[str, Any]
    source: SourceLocation


@dataclass(frozen=True)
class ChoiceRow:
    index: int
    list_name: str | None
    name: str | None
    values: Mapping[str, Any]
    source: SourceLocation


@dataclass(frozen=True)
class Diagnostic:
    rule_id: str
    severity: Severity
    message: str
    source: SourceLocation | None
    origin: Literal["pyxform", "native"]
    help: str | None = None
    related: tuple[SourceLocation, ...] = ()
```

The exact code is not frozen, but these concepts are.

---

## 8. Rule namespace and ID strategy

Rule IDs must be stable from V1 onward.

Changing implementation should not unnecessarily change rule IDs.

### 8.1 Proposed prefixes

| Prefix | Category |
|---|---|
| `PX` | normalized pyxform validation |
| `CHO` | choices / choice-list hygiene |
| `LBL` | labels / visible text |
| `I18N` | language / translation coverage |
| `UX` | form-authoring / field-user experience |
| `ORD` | ordering / timing smells |

IDs use three digits:

```text
PX001
CHO001
LBL001
I18N001
UX001
ORD001
```

### 8.2 Stability rule

Once released in V1:

- a rule ID must retain its meaning;
- a semantically different check receives a new ID;
- deprecated rules remain documented;
- formatters must not invent rule IDs dynamically.

---

## 9. Frozen V1 rule catalog

### 9.1 Normalized pyxform diagnostics

These are not independently reimplemented unless source mapping requires supplementary parsing.

#### `PX001` — duplicate name in scope

**Origin:** pyxform  
**Default severity:** error

Normalize pyxform failures for duplicate question/group/repeat names that are invalid **within the applicable XLSForm scope**. XLSForm-lint must not implement this as a naïve workbook-wide duplicate-name check: the same `name` may legitimately occur in distinct parent groups/repeats when pyxform permits it.

The semantic authority for whether a duplicate is invalid remains pyxform. The linter's responsibility is to normalize that failure into a stable rule ID and enrich it with workbook source locations.

Example of a same-scope duplicate that pyxform rejects:

```text
survey row 10: name = household_id
survey row 31: name = household_id
```

Expected style:

```text
PX001 error duplicate-name-in-scope
survey:31:name: 'household_id' duplicates another name in the same XLSForm scope.
```

When the earlier conflicting definition can be identified unambiguously, attach it as a related location, for example `survey:10:name`. Do not guess a related location when scope resolution is ambiguous.

**V1 invariant:** no native rule may independently flag duplicate survey names globally. `PX001` is emitted only from a pyxform-rejected duplicate condition (plus deterministic source-location enrichment).

---

#### `PX002` — invalid survey name

**Origin:** pyxform  
**Default severity:** error

Normalize invalid field/XML identifier failures detected upstream.

Do not invent an independent identifier grammar if pyxform already defines validity.

---

#### `PX003` — missing required structural value

**Origin:** pyxform  
**Default severity:** error

Normalize upstream failures for missing required structural fields such as invalid blank `type`/`name` combinations.

The linter should preserve pyxform semantics rather than maintaining a parallel exception table.

---

#### `PX004` — unknown internal choice list

**Origin:** pyxform  
**Default severity:** error

Normalize select questions whose internal list cannot be resolved.

Example:

```text
select_one region_list
```

when no appropriate `region_list` exists in `choices`.

---

#### `PX005` — unknown field reference

**Origin:** pyxform  
**Default severity:** error

Normalize unresolved `${field}` references.

`xlsform-lint` should add a typo suggestion when one candidate is sufficiently close.

Example:

```text
PX005 error unknown-field-reference
survey:14:relevant: 'age_yrs' does not exist. Did you mean 'age_years'?
```

##### Suggestion behavior

Suggestion logic must be conservative.

V1 recommendation:

- compare against valid survey names;
- use a deterministic edit-distance or similarity function;
- emit at most one suggestion;
- suppress suggestions below a defined confidence threshold;
- never silently rewrite the reference.

---

#### `PX006` — duplicate choice value

**Origin:** pyxform  
**Default severity:** error

Normalize duplicate choice-name failures.

**Required exception:** honor XLSForm setting:

```text
allow_choice_duplicates = yes
```

When pyxform considers the duplicate valid under that setting, `xlsform-lint` must not reintroduce it as an error.

---

## 9.2 Native lint rules

### `CHO001` — unused internal choice list

**Origin:** native  
**Default severity:** warning

Flag a choice list defined in the `choices` sheet that is not referenced by a recognized internal select question.

Example:

```text
CHO001 warning unused-choice-list
choices:22:list_name: list 'yesno_extra' is defined but is not referenced by an internal select.
```

#### Required safeguards

V1 must avoid naïve set subtraction.

The rule must distinguish at minimum:

- ordinary `select_one <list>`;
- ordinary `select_multiple <list>`;
- dynamic list references;
- external selects or external files;
- constructs the parser cannot safely classify.

If usage is ambiguous, prefer **no warning** rather than a false positive.

#### Rationale

This rule identifies:

- stale form content;
- abandoned lists;
- copy/paste leftovers;
- renamed select questions;
- author assumptions that a list remains live.

---

### `LBL001` — missing visible question label

**Origin:** native  
**Default severity:** warning

Flag a visible question without a usable label.

The check is type-aware.

#### Initial V1 classification

| Type/category | Missing label behavior |
|---|---|
| ordinary visible question | warning |
| `note` | warning |
| `calculate` | allowed |
| `hidden` | allowed |
| metadata/internal type | allowed or type-specific |
| group/repeat | do not over-enforce in V1 unless clearly visible and label-bearing |

The implementation should centralize type classification rather than spreading exclusions across rules.

---

### `LBL002` — blank choice label

**Origin:** native  
**Default severity:** warning

Flag a choice row that has a valid `name` but no usable label in the active/default label context.

Example:

```text
LBL002 warning blank-choice-label
choices:25:label: choice 'north' in list 'region' has no label.
```

For multilingual forms, interaction with `I18N` rules must avoid duplicate noise where possible.

---

### `I18N001` — incomplete translation coverage

**Origin:** native  
**Default severity:** warning

When multiple language-specific label columns are present, identify rows where one language has content and another expected language is blank.

Example columns:

```text
label::English
label::French
```

Potential diagnostic:

```text
I18N001 warning incomplete-translation
survey:42:label::French: translation is missing while label::English is populated.
```

#### V1 scope

Primary scope is `label::Language` columns.

The architecture should allow future expansion to:

- `hint::Language`;
- `constraint_message::Language`;
- `required_message::Language`;
- other translatable columns.

Do not silently infer that every arbitrary `::` column is a label translation.

#### Noise control

Rules should avoid flagging rows where the underlying type does not require/display the translatable value.

---

### `UX001` — constraint without constraint message

**Origin:** native  
**Default severity:** warning

Flag a row where a `constraint` is defined but no corresponding constraint message is present.

Example:

```text
UX001 warning constraint-without-message
survey:9:constraint: constraint is set but constraint_message is empty.
```

For multilingual forms, a future extension may analyze per-language message coverage. V1 may emit the basic diagnostic only.

#### Rationale

The form may remain valid, but field users may receive poor or opaque validation feedback.

---

### `ORD001` — choice filter depends on later-defined field

**Origin:** native  
**Default severity:** warning

This is intentionally **not** a generic later-reference rule.

V1 only inspects `choice_filter` dependencies where a referenced survey field is defined later in form order and therefore may not yet have a value when the select question is first reached.

Example:

```text
survey row 18: select_one village / choice_filter = district=${district}
survey row 31: select_one district / name = district
```

Potential diagnostic:

```text
ORD001 warning later-choice-filter-dependency
survey:18:choice_filter: depends on '${district}', defined later at survey row 31.
The filter may evaluate before that value is populated.
```

#### Important safeguards

This is a timing smell, not proof of invalid logic.

V1 should avoid warning when it can confidently determine the value is already available through a supported earlier mechanism.

If that determination becomes complex, bias toward reduced coverage rather than broad false-positive behavior.

#### Explicitly not included

Do not extend this V1 rule to all of:

- `relevant`;
- `constraint`;
- `calculate`;
- arbitrary XPath;

without a separate future design review.

---

### `UX002` — required question has a default

**Origin:** native  
**Default severity:** info  
**Strict profile severity:** warning

Flag rows where:

```text
required = yes
```

and a non-empty default value is also provided.

Potential diagnostic:

```text
UX002 info required-with-default
survey:27:required: required question also has a default value; confirm that the default is intentional.
```

This is not intrinsically incorrect XLSForm and must not be an error.

---

## 10. Severity model

V1 supports exactly:

```text
error
warning
info
```

### 10.1 Default behavior

- `error`: causes non-zero lint failure by default.
- `warning`: reported but does not fail by default.
- `info`: reported only according to output/profile behavior defined below.

### 10.2 Severity overrides

Users can override native rule severity through config.

Example:

```toml
[rules]
UX001 = "error"
UX002 = "off"
I18N001 = "warning"
```

For normalized pyxform validity errors, V1 should be conservative about allowing downgrade below `error`.

Recommended V1 policy:

- pyxform-backed `PX*` errors can be disabled from reporting only if technically necessary for advanced workflows, but they cannot be reclassified as valid form output;
- native rules can be `error`, `warning`, `info`, or `off`.

If this creates implementation complexity, freeze PX rules as non-overridable errors in V1 and document it.

---

## 11. Profiles

V1 should support at least two profiles conceptually:

### `default`

Normal low-noise behavior.

Example:

- `UX002` = info.

### `strict`

More opinionated authoring policy.

Example:

- `UX002` = warning.

CLI:

```bash
xlsform-lint form.xlsx --profile strict
```

If profile implementation would materially delay the first release, V1 may launch with `default` plus configuration-based overrides, but the config model must not block profiles later.

---

## 12. CLI contract

### 12.1 Basic command

```bash
xlsform-lint path/to/form.xlsx
```

### 12.2 Core V1 options

```text
xlsform-lint FORM.xlsx
    [--format text|json|sarif]
    [--config PATH]
    [--select RULES]
    [--ignore RULES]
    [--profile default|strict]
    [--fail-on error|warning|info]
    [--quiet]
    [--version]
```

### 12.3 Rule selection

Examples:

```bash
xlsform-lint form.xlsx --select I18N,LBL
xlsform-lint form.xlsx --ignore UX002
xlsform-lint form.xlsx --select PX005,CHO001
```

V1 selection grammar should support:

- exact rule ID;
- category prefix.

Avoid glob complexity unless needed.

### 12.4 Precedence

Recommended precedence from lowest to highest:

```text
built-in defaults
→ selected profile
→ .xlsform-lint.toml
→ explicit CLI options
```

Document precedence and test it.

---

## 13. Configuration contract

Default config filename:

```text
.xlsform-lint.toml
```

V1 should search from the current working directory or input file directory upward using a clearly documented rule. Avoid surprising cross-project discovery.

### Example configuration

```toml
profile = "default"

[lint]
fail_on = "error"
format = "text"

[rules]
UX001 = "error"
UX002 = "off"
I18N001 = "warning"

[select]
include = ["PX", "CHO", "LBL", "I18N", "UX", "ORD"]
ignore = []
```

The final schema may be simplified, but V1 must support:

- rule enable/disable;
- native severity override;
- fail threshold;
- optional profile selection.

Unknown config keys should fail clearly rather than being silently ignored.

---

## 14. Text output contract

Default output should be concise, stable, and source-oriented.

Example:

```text
form.xlsx:survey:14:relevant
PX005 error unknown-field-reference: 'age_yrs' does not exist. Did you mean 'age_years'?

form.xlsx:choices:22:list_name
CHO001 warning unused-choice-list: list 'yesno_extra' is defined but is not referenced by an internal select.

form.xlsx:survey:9:constraint
UX001 warning constraint-without-message: constraint is set but constraint_message is empty.

1 error, 2 warnings
```

A compact single-line mode may be added later, but the V1 default should prioritize readability.

### Requirements

- diagnostics sorted deterministically;
- paths normalized predictably;
- no timestamps in normal output;
- no nondeterministic object representations;
- summary counts always stable;
- rule ID always visible.

---

## 15. JSON output contract

Command:

```bash
xlsform-lint form.xlsx --format json
```

Illustrative schema:

```json
{
  "version": 1,
  "file": "form.xlsx",
  "diagnostics": [
    {
      "rule_id": "UX001",
      "severity": "warning",
      "message": "constraint is set but constraint_message is empty.",
      "origin": "native",
      "location": {
        "sheet": "survey",
        "row": 9,
        "column": "constraint",
        "cell": "G9"
      }
    }
  ],
  "summary": {
    "errors": 0,
    "warnings": 1,
    "info": 0
  }
}
```

### JSON stability

The top-level schema must include a version number from day one.

Breaking schema changes require a version bump.

JSON output must contain no human decoration, ANSI codes, or progress messages.

---

## 16. SARIF output contract

Command:

```bash
xlsform-lint form.xlsx --format sarif
```

V1 SARIF should be sufficient for GitHub code-scanning compatible ingestion where practical.

Map:

```text
rule_id   → SARIF rule ID
severity  → SARIF level
message   → SARIF message
cell/row  → source region/location where representable
```

Because `.xlsx` is not ordinary source text, V1 should document any limitations of GitHub's annotation rendering for workbook files.

The important requirement is that SARIF is syntactically valid, deterministic, and preserves rule identity/location metadata.

---

## 17. Exit-code contract

V1 exit codes must be documented and stable.

Recommended:

| Exit code | Meaning |
|---:|---|
| `0` | lint completed; no diagnostic at or above fail threshold |
| `1` | lint completed; diagnostic met/exceeded fail threshold |
| `2` | tool/config/input usage error or unreadable/invalid invocation |
| `3` | internal unexpected linter failure |

Default fail threshold:

```text
error
```

Examples:

```bash
xlsform-lint form.xlsx
```

Warnings only → exit `0`.

```bash
xlsform-lint form.xlsx --fail-on warning
```

Warning → exit `1`.

Do not use a different exit code for each rule.

---

## 18. Source mapping requirements

Source locations are a first-class V1 feature.

### 18.1 Minimum source fields

For any diagnostic tied to a workbook element, attempt to report:

- workbook path;
- sheet;
- row;
- logical column name;
- Excel cell coordinate when available.

Example:

```text
survey row 14, column relevant, cell H14
```

### 18.2 Duplicate diagnostics

For duplicate definitions, support related locations when practical:

```text
duplicate at survey!B31
first defined at survey!B10
```

### 18.3 Pyxform diagnostic mapping

If a pyxform error does not identify an exact location, the adapter may use diagnostic content plus the normalized workbook model to locate likely source rows.

Rules:

1. mapping must be deterministic;
2. never fabricate a precise cell if confidence is low;
3. fall back to sheet-level or file-level location when exact mapping is unsafe.

---

## 19. Diagnostic normalization strategy

V1 should isolate pyxform-specific strings and exceptions inside `pyxform_adapter.py` or equivalent.

Native rule code must not parse pyxform error strings.

Conceptual flow:

```text
pyxform exception/result
        │
        ▼
adapter recognizes known semantic class
        │
        ▼
PX rule ID + normalized message
        │
        ▼
source mapper enriches location
        │
        ▼
Diagnostic
```

### Unknown pyxform error behavior

Do not silently discard upstream failures that have no mapping yet.

V1 should emit a generic normalized diagnostic such as:

```text
PX999 error pyxform-validation-error
<sanitized upstream message>
```

`PX999` is a fallback, not a substitute for mapping common errors.

This preserves correctness when pyxform introduces new checks.

---

## 20. Handling pyxform version drift

Since pyxform is a semantic dependency, V1 must account for upstream changes.

### Requirements

- pin or constrain supported pyxform versions deliberately;
- test against the supported range;
- expose the installed pyxform version in `--version` or debug metadata;
- do not silently depend on undocumented internal APIs without adapter isolation;
- add fixtures for each pyxform diagnostic the project normalizes.

Example:

```text
xlsform-lint 0.1.0
pyxform 4.x.y
```

If pyxform changes an error message while preserving semantics, only the adapter tests should ideally require repair.

---

## 21. Parsing strategy

### 21.1 Workbook pass

The source-oriented reader should:

1. open workbook read-only where practical;
2. identify `survey`, `choices`, and `settings` sheets case/format according to supported XLSForm conventions;
3. read headers without mutating them;
4. preserve original row numbers;
5. construct normalized column lookup;
6. retain raw values required for diagnostics.

### 21.2 Semantic pass

Call supported pyxform APIs to obtain canonical validation behavior.

Do not rely on launching a shell command if a stable Python API is available.

### 21.3 Native model pass

Build indexes such as:

```text
survey_by_name
choice_lists
choice_rows_by_list
select_usage
language_columns
survey_order
```

Only build semantic indexes required by frozen V1 rules.

---

## 22. Dynamic/external choice safety

`CHO001` must not accidentally label external or dynamically resolved lists as unused.

The select classifier should distinguish known categories.

Illustrative internal enum:

```text
INTERNAL_STATIC
INTERNAL_DYNAMIC
EXTERNAL_FILE
UNKNOWN
```

Only `INTERNAL_STATIC` lists should be eligible for the ordinary unused-list check unless future support explicitly expands the rule.

Unknown syntax should produce no `CHO001` result.

---

## 23. Translation model

V1 needs a deterministic parser for multilingual label columns.

Recognize patterns such as:

```text
label::English
label::French
```

Normalize the underlying base key separately from language name.

Example:

```text
base = label
language = English
```

Do not normalize language names so aggressively that distinct headers collapse unexpectedly.

V1 should preserve original header spelling in diagnostics.

---

## 24. Rule suppression strategy

V1 supports global/config/CLI suppression.

It does **not** need inline workbook suppression comments in the initial release.

Supported mechanisms:

```bash
xlsform-lint form.xlsx --ignore UX002
```

or:

```toml
[rules]
UX002 = "off"
```

Per-row suppression, spreadsheet comments such as `# noqa`, and waiver files may be evaluated later.

---

## 25. Deterministic ordering

Diagnostics should sort by:

1. file path;
2. sheet order (`survey`, `choices`, `settings`, then lexical fallback);
3. row number;
4. column position/name;
5. rule ID;
6. message as final deterministic tie-breaker.

This makes CI diffs stable.

---

## 26. Pre-commit integration

V1 should document a standard pre-commit configuration.

Illustrative:

```yaml
repos:
  - repo: https://github.com/<owner>/xlsform-lint
    rev: v0.1.0
    hooks:
      - id: xlsform-lint
        files: \.xlsx$
```

Hook behavior:

- read-only;
- one or multiple matching workbooks;
- fail according to default or configured threshold;
- no network requirement after dependencies are installed.

If multi-file CLI support is not implemented in the first release, pre-commit may invoke once per file.

---

## 27. GitHub Actions integration

Two acceptable V1 forms:

### Option A — standard Python install

```yaml
- name: Install XLSForm Lint
  run: pip install xlsform-lint

- name: Lint XLSForms
  run: xlsform-lint forms/main.xlsx --fail-on warning
```

### Option B — dedicated action wrapper

```yaml
- uses: <owner>/xlsform-lint-action@v1
  with:
    path: forms/main.xlsx
```

For V1, Option A is sufficient if a dedicated Action would delay the core package. However, the README must contain a copy-paste CI recipe from the first release.

SARIF upload may be documented as an advanced example.

---

## 28. Testing strategy

Testing is a major acceptance requirement because rule correctness is the product.

### 28.1 Unit tests

Cover:

- config parsing;
- severity precedence;
- rule selection;
- source mapping;
- typo suggestion threshold;
- translation column parsing;
- select/list classification;
- deterministic sorting;
- each formatter;
- exit-code calculation.

### 28.2 Rule fixture tests

Each rule gets at least:

- one positive fixture that must trigger;
- one valid nearby fixture that must not trigger;
- one edge/exception fixture when applicable.

Examples:

#### `PX006`

1. duplicate choices without setting → error;
2. duplicate choices with `allow_choice_duplicates=yes` → no duplicate error.

#### `CHO001`

1. static unused list → warning;
2. used static list → no warning;
3. dynamic/external construct → no false positive.

#### `ORD001`

1. later choice-filter dependency → warning;
2. earlier dependency → no warning;
3. unrelated later references elsewhere → no warning.

### 28.3 Integration tests

Run complete CLI commands over real `.xlsx` fixtures.

Assert:

- stdout/stderr;
- exact exit code;
- JSON schema;
- SARIF validity;
- config discovery;
- deterministic output.

### 28.4 Golden tests

Maintain canonical text/JSON/SARIF outputs for selected representative workbooks.

Golden outputs make accidental diagnostic-contract changes visible in review.

---

## 29. Representative fixture matrix

V1 should include compact synthetic fixtures for:

```text
valid_minimal.xlsx
valid_multilingual.xlsx
valid_duplicate_choices_allowed.xlsx
invalid_duplicate_name.xlsx
invalid_unknown_reference.xlsx
invalid_missing_choice_list.xlsx
lint_unused_choice_list.xlsx
lint_missing_label.xlsx
lint_blank_choice_label.xlsx
lint_incomplete_translation.xlsx
lint_constraint_without_message.xlsx
lint_later_choice_filter_dependency.xlsx
lint_required_with_default.xlsx
```

Where licensing permits, add anonymized or purpose-built larger forms representative of ODK/Kobo usage.

Do not copy proprietary customer forms into the test suite.

---

## 30. Performance target

V1 is not performance-critical in the same way as a source-code linter, but it should feel immediate for normal XLSForms.

Initial qualitative target:

> A normal form with hundreds to low-thousands of rows should lint in ordinary interactive CLI time without noticeable avoidable delay.

Do not optimize prematurely.

Performance regression tests can be added once realistic fixture sizes exist.

---

## 31. Security and file-safety requirements

`xlsform-lint` processes potentially untrusted `.xlsx` files.

V1 should:

- never execute spreadsheet macros;
- never evaluate Excel formulas through Excel;
- not follow external workbook links;
- avoid network access;
- not invoke shell commands using workbook-controlled strings;
- treat displayed diagnostic text as untrusted input;
- remain read-only.

Formula cells may be inspected as stored text/value where needed, but no general Excel calculation engine should be introduced.

---

## 32. Error handling

Differentiate:

### User/input errors

Examples:

- file does not exist;
- file is not a readable `.xlsx` workbook;
- config is malformed;
- unsupported CLI argument.

Exit `2`.

### Lint/validation findings

Expected diagnostics.

Exit `0` or `1` according to threshold.

### Internal failures

Unexpected exception indicating a bug.

Exit `3`.

Provide a concise error with optional debug traceback controlled by a future/debug flag. Do not dump a traceback by default for ordinary invalid forms.

---

## 33. Versioning

Use semantic versioning for the package.

Before `1.0.0`, rule behavior may still evolve, but diagnostic IDs should already be treated as compatibility-sensitive.

Potential release path:

```text
0.1.0  first usable V1 implementation
0.2.x  rule hardening / compatibility
1.0.0  stable CLI + diagnostic contract
```

The term "V1" in this blueprint refers to the product scope, not necessarily package version `1.0.0` on first publication.

---

## 34. Documentation requirements

The first public release should contain:

### README

- what the tool is;
- what it is not;
- installation;
- five-minute usage;
- output example;
- CI example;
- configuration example;
- supported pyxform version;
- links to rules.

### `docs/rules.md`

For every rule:

- ID;
- name;
- severity;
- origin;
- rationale;
- bad example;
- valid/exception example;
- configuration notes.

### `docs/configuration.md`

Document:

- config discovery;
- precedence;
- `--select`;
- `--ignore`;
- severity override;
- fail threshold.

### Integration docs

- pre-commit;
- GitHub Actions;
- SARIF example if supported satisfactorily.

---

## 35. README-level user experience example

```bash
$ xlsform-lint forms/household-survey.xlsx

forms/household-survey.xlsx:survey:14:relevant
PX005 error unknown-field-reference: 'age_yrs' does not exist. Did you mean 'age_years'?

forms/household-survey.xlsx:choices:22:list_name
CHO001 warning unused-choice-list: list 'yesno_extra' is defined but is not referenced by an internal select.

forms/household-survey.xlsx:survey:9:constraint
UX001 warning constraint-without-message: constraint is set but constraint_message is empty.

1 error, 2 warnings
```

CI:

```bash
xlsform-lint forms/household-survey.xlsx --fail-on warning
```

Machine output:

```bash
xlsform-lint forms/household-survey.xlsx --format json
xlsform-lint forms/household-survey.xlsx --format sarif
```

---

## 36. V1 implementation phases

### Phase 0 — repository and dependency spike

Goal: prove the architecture before rule implementation.

Deliverables:

- Python package skeleton;
- CLI entry point;
- supported Python version decision;
- pyxform dependency integrated;
- workbook reader integrated;
- one known pyxform error captured;
- exact workbook row/cell location demonstrated on one fixture;
- dependency/licensing review.

**Gate:** prove that pyxform diagnostics and source mapping can coexist without fragile architecture.

---

### Phase 1 — diagnostic kernel

Deliver:

- `Diagnostic` model;
- source-location model;
- severity model;
- deterministic sorting;
- text formatter;
- core exit-code logic;
- generic pyxform fallback `PX999`.

**Gate:** one invalid workbook produces a normalized stable diagnostic and correct exit code.

---

### Phase 2 — normalized pyxform rules

Implement mappings for:

```text
PX001 duplicate name in scope
PX002 invalid survey name
PX003 missing structural value
PX004 missing choice list
PX005 unknown field reference
PX006 duplicate choice value
```

Add typo suggestion for `PX005`.

**Gate:** fixture matrix passes, including `allow_choice_duplicates=yes` exception.

---

### Phase 3 — native lint model and rules

Implement:

```text
CHO001
LBL001
LBL002
I18N001
UX001
ORD001
UX002
```

**Gate:** each rule has positive, negative, and relevant edge-case tests.

---

### Phase 4 — configuration and profiles

Implement:

- `.xlsform-lint.toml`;
- config validation;
- `--select`;
- `--ignore`;
- severity overrides;
- fail threshold;
- `default` and, if retained, `strict` profile.

**Gate:** precedence is documented and integration-tested.

---

### Phase 5 — machine-readable outputs

Implement:

- versioned JSON schema;
- SARIF;
- golden-output tests.

**Gate:** deterministic output and schema validation.

---

### Phase 6 — integration packaging

Deliver:

- pre-commit metadata/docs;
- GitHub Actions recipe;
- package installation docs;
- console script packaging;
- release workflow.

**Gate:** clean repository can install the released artifact and lint a fixture in CI.

---

### Phase 7 — V1 hardening and release candidate

Perform:

- full test suite;
- clean-environment install;
- representative larger-form testing;
- documentation audit;
- rule false-positive review;
- Windows/macOS/Linux compatibility review if supported by CI;
- package metadata/license checks;
- public API/CLI freeze.

**Gate:** V1 acceptance checklist below passes.

---

## 37. V1 acceptance checklist

V1 is complete only when all applicable items pass.

### Core behavior

- [ ] `xlsform-lint form.xlsx` works on a valid form.
- [ ] Core pyxform failures are normalized into stable `PX*` IDs.
- [ ] Unknown upstream failures are not swallowed.
- [ ] Native frozen rules are implemented.
- [ ] `allow_choice_duplicates=yes` is honored.
- [ ] Dynamic/external selects do not create obvious `CHO001` false positives.
- [ ] `ORD001` is restricted to the frozen choice-filter timing smell.
- [ ] ordinary cross-group references are not warned on merely for crossing groups.

### Diagnostics

- [ ] diagnostics include rule ID;
- [ ] diagnostics include severity;
- [ ] diagnostics include origin;
- [ ] exact sheet/row/column/cell location is emitted where safely available;
- [ ] ordering is deterministic;
- [ ] typo suggestions are deterministic and conservative.

### Output

- [ ] text output implemented;
- [ ] JSON output implemented and versioned;
- [ ] SARIF output implemented and validated;
- [ ] no ANSI/noise leaks into JSON or SARIF;
- [ ] summary counts are correct.

### Configuration

- [ ] `.xlsform-lint.toml` works;
- [ ] invalid config fails clearly;
- [ ] `--select` works;
- [ ] `--ignore` works;
- [ ] severity overrides work for supported rules;
- [ ] `--fail-on` works;
- [ ] precedence is tested.

### CI/dev tooling

- [ ] deterministic exit-code contract implemented;
- [ ] pre-commit usage documented and tested;
- [ ] GitHub Actions usage documented and tested;
- [ ] clean installation works from built package.

### Safety and boundaries

- [ ] input workbook is never rewritten;
- [ ] no Java dependency introduced;
- [ ] no network dependency required for lint execution;
- [ ] no runtime XPath/form scenario execution;
- [ ] no external CSV analysis;
- [ ] no autofix;
- [ ] no broad repeat-scope implementation.

### Documentation

- [ ] README complete;
- [ ] rule catalog complete;
- [ ] configuration reference complete;
- [ ] examples use stable rule IDs;
- [ ] relationship to pyxform is explained accurately;
- [ ] project does not market itself as "catching everything pyxform misses."

---

## 38. Deferred post-V1 opportunities

These are intentionally not part of the frozen V1 scope.

### Additional lint rules

- repeat-scope analysis;
- broader expression dependency analysis;
- unused questions/calculates;
- unreachable relevance patterns;
- duplicate or suspicious labels;
- choice-order consistency;
- suspicious defaults;
- missing hints or help text under configurable policy;
- translation coverage for hints/messages;
- naming conventions;
- settings-sheet policy rules;
- overly large choice lists;
- media-reference hygiene.

### Ecosystem integration

- VS Code extension;
- GitHub annotation helper;
- dedicated GitHub Action;
- Language Server Protocol integration;
- editor diagnostics while authoring XLSForm source tables;
- web/drag-and-drop lint UI.

### Baselines and suppressions

- baseline files for legacy forms;
- per-rule waivers;
- inline/workbook suppression metadata;
- "new diagnostics only" CI mode.

### Autofix

Only after diagnostics prove stable and safe fix classes are identified.

Potential safe fixes could eventually include purely mechanical cleanup, but workbook mutation requires a separate design and safety review.

### Behavioral testing

Separate future product direction:

```text
xlsform-test
```

for scenario execution, expected visibility, calculations, constraints, and workflow assertions.

---

## 39. Strategic moat

The project should not define its moat as owning more validation rules than pyxform.

That is fragile because upstream validation should improve over time.

The durable layer is:

1. **stable diagnostics** — rule IDs that teams can depend on;
2. **developer workflow** — CLI, config, pre-commit, CI;
3. **machine output** — JSON and SARIF;
4. **source precision** — spreadsheet cell-aware diagnostics;
5. **quality policy** — valid-but-suspicious rules beyond converter correctness;
6. **low-noise trust** — conservative rules with documented exceptions;
7. **ecosystem extensibility** — future editor, baseline, and test-tool integration.

This allows `xlsform-lint` to improve when pyxform improves rather than becoming obsolete because of it.

---

## 40. V1 scope freeze

The following statement defines the implementation boundary:

> **V1 of `xlsform-lint` will be a read-only Python CLI that uses pyxform as the canonical XLSForm semantic validator, enriches upstream failures with stable `PX*` rule IDs and spreadsheet source locations, and adds seven conservative native lint rules covering unused internal choice lists, labels, translation completeness, constraint messages, one narrowly scoped choice-filter ordering smell, and required-with-default hygiene. It will support text, JSON, and SARIF output; deterministic exit codes; configuration, rule selection, and severity policy; and documented pre-commit/GitHub Actions workflows. It will not execute form logic, validate external datasets, autofix spreadsheets, perform broad repeat-scope analysis, or flag ordinary cross-group references.**

Any proposed implementation work outside that sentence requires an explicit V1 scope change.

---

## 41. Recommended first implementation checkpoint

Before coding the full rule engine, run a bounded architecture spike answering exactly these questions:

1. Which supported pyxform API provides the cleanest validation entry point without Java/runtime form execution?
2. Which core failures can be captured as structured exceptions versus string-only messages?
3. Can the linter reliably map the following back to workbook cells?
   - duplicate name rejected within XLSForm scope;
   - missing list;
   - unknown `${field}` reference;
   - duplicate choice name.
4. Is `openpyxl` sufficient for source mapping without conflicting with pyxform's workbook interpretation?
5. What minimum supported Python and pyxform versions should be frozen?
6. Can a representative valid ODK/Kobo form pass through the dual-reader architecture without semantic mismatch?

The implementation should proceed beyond the spike only if those answers support a stable adapter boundary.

---

## 42. One-line repository description

Recommended GitHub description:

> **Deterministic linting for XLSForm — stable diagnostics, quality rules, source locations, config, and CI on top of pyxform.**

Alternative short tagline:

> **Ruff-style linting for ODK/Kobo XLSForms.**

---

## 43. Final V1 decision

**GO.**

The project is worth implementing as a focused developer tool, provided the scope remains centered on the tooling layer rather than duplicating pyxform's semantic responsibility.

The most important V1 success criterion is not the number of rules. It is whether users can trust this command in a repository:

```bash
xlsform-lint form.xlsx
```

and receive stable, low-noise, source-precise diagnostics that behave predictably on a laptop, in pre-commit, and in CI.
