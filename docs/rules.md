# Rule catalog

pyxform is the semantic authority for every `PX` rule. PX diagnostics always
have severity `error`, cannot be severity-overridden, and preserve only source
precision supported by workbook evidence. Selection can hide their reporting,
but a hidden fatal PX result still exits 1.

## Pyxform diagnostics

### PX001 — Duplicate name in scope

- **Origin/default:** pyxform; error.
- **Purpose:** normalize pyxform's duplicate survey-name failure.
- **Bad:** two `name` cells contain `household` in the same XLSForm scope.
- **Valid/exception:** the same name where pyxform permits it in distinct scopes.
- **Safeguard:** scope semantics are not recreated; a related cell is attached
  only for one unambiguous lexical predecessor.
- **Configuration/source:** reporting is selectable; severity is fixed. The
  failing name cell is exact when uniquely identifiable.

### PX002 — Invalid survey name

- **Origin/default:** pyxform; error.
- **Purpose:** report a field name that violates XLSForm naming syntax.
- **Bad:** `1person`; **valid:** `person_1`.
- **Safeguard:** the trigger remains pyxform's failure, not a parallel validator.
- **Configuration/source:** reporting is selectable; severity is fixed. Exact
  name-cell location is used only when supported.

### PX003 — Missing required structural value

- **Origin/default:** pyxform; error.
- **Purpose:** normalize a missing survey `name` or `type` required by pyxform.
- **Bad:** a question row with a blank `type`; **valid:** `text`, `person`, `Name`.
- **Safeguard:** no missing-value cases beyond observed pyxform failures are
  invented.
- **Configuration/source:** reporting is selectable; severity is fixed. A row
  location is reported without fabricating an exact blank cell.

### PX004 — Unknown internal choice list

- **Origin/default:** pyxform; error.
- **Purpose:** report an internal select whose list is absent from `choices`.
- **Bad:** `select_one regions` without list `regions`; **valid:** a matching list.
- **Safeguard:** external/dynamic select syntax is left to pyxform.
- **Configuration/source:** reporting is selectable; severity is fixed. The
  survey `type` cell is exact when uniquely identifiable.

### PX005 — Unknown field reference

- **Origin/default:** pyxform; error.
- **Purpose:** normalize references such as `${agge}` when no field exists.
- **Bad:** `${agge} > 17`; **valid:** `${age} > 17` when `age` exists.
- **Safeguard:** a “Did you mean” suggestion appears only for one strong,
  unambiguous lexical match; runtime XPath correctness is not evaluated.
- **Configuration/source:** reporting is selectable; severity is fixed. Exact
  source is used only when the referenced token occurs in one matching cell.

### PX006 — Duplicate choice value

- **Origin/default:** pyxform; error.
- **Purpose:** normalize duplicate choice names within one list.
- **Bad:** two `yesno` choices named `yes`; **valid:** unique names, or duplicates
  accepted by pyxform when `allow_choice_duplicates=yes` is intentionally set.
- **Safeguard:** pyxform owns the setting and list semantics.
- **Configuration/source:** reporting is selectable; severity is fixed. Exact and
  related choice-name cells are used only when unambiguous.

### PX999 — Unrecognized pyxform failure

- **Origin/default:** pyxform; error.
- **Purpose:** fallback for unrecognized upstream semantic failures.
- **Bad:** any fatal pyxform error outside PX001–PX006; **valid:** successful
  pyxform conversion.
- **Safeguard:** preserves the sanitized upstream message, reports only the first
  fatal failure, and does not infer cell precision.
- **Configuration/source:** reporting is selectable; severity is fixed; source is
  file-level.

## Native diagnostics

### CHO001 — Unused internal choice list

- **Origin/default:** native; warning.
- **Purpose/bad:** report a defined internal list unused by any static select.
- **Valid/exception:** every list is used by `select_one`/`select_multiple`.
- **Safeguard:** dynamic, external, unknown select syntax, or an unresolved static
  list suppresses the rule to avoid claiming a list is unused unsafely.
- **Configuration/source:** severity can be changed or disabled; selection
  applies. Reports the first row of the unused list at exact `list_name` cell.

### LBL001 — Missing visible-question label

- **Origin/default:** native; warning.
- **Purpose/bad:** report a visible question or note whose label is blank.
- **Valid/exception:** a populated label; calculate, hidden, metadata, containers,
  and unknown types are not label-bearing for this rule.
- **Safeguard:** translated label columns take precedence and ambiguous headers
  suppress dependent checks.
- **Configuration/source:** configurable/selectable; exact label cell.

### LBL002 — Blank choice label

- **Origin/default:** native; warning.
- **Purpose/bad:** report a named choice with no label.
- **Valid/exception:** a populated label; blank structural rows and choices
  without a name are ignored.
- **Safeguard:** translated labels take precedence; ambiguous headers suppress
  dependent checks.
- **Configuration/source:** configurable/selectable; exact label cell.

### I18N001 — Incomplete translation

- **Origin/default:** native; warning.
- **Purpose/bad:** report one blank translated label when another language is
  populated on the same label-bearing row.
- **Valid/exception:** all translated labels populated, all blank, or only one
  translated language column.
- **Safeguard:** applies only to label-bearing survey rows and named choices;
  unrelated `::language` columns are ignored.
- **Configuration/source:** configurable/selectable; exact missing-language cell.

### UX001 — Constraint without message

- **Origin/default:** native; warning.
- **Purpose/bad:** report a nonblank `constraint` with no populated plain or
  translated `constraint_message`.
- **Valid/exception:** any corresponding message is populated, or no constraint.
- **Safeguard:** ambiguous message headers suppress the check.
- **Configuration/source:** configurable/selectable; exact constraint cell.

### ORD001 — Later choice-filter dependency

- **Origin/default:** native; warning.
- **Purpose/bad:** report `${later}` in `choice_filter` when the unique named field
  is lexically later.
- **Valid/exception:** earlier references and references in `relevant`,
  `constraint`, or `calculation` are outside this narrow rule.
- **Safeguard:** any group/repeat structure or ambiguous field definition
  suppresses the check; ordinary cross-group references are never generically
  warned.
- **Configuration/source:** configurable/selectable; exact filter cell and one
  exact related name cell when available.

### UX002 — Required question with default

- **Origin/default:** native; info in `default`, warning in `strict`.
- **Purpose/bad:** flag `required=yes` together with a nonblank default for review.
- **Valid/exception:** required without default, default without required, or a
  blank default.
- **Safeguard:** only the exact normalized `yes` value triggers it.
- **Configuration/source:** configurable/selectable; exact required cell.
