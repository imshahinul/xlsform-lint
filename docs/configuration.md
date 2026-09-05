# Configuration reference

## Discovery and precedence

The optional configuration filename is `.xlsform-lint.toml`. For an implicit
configuration, discovery starts in the input workbook's directory and walks up
its ancestors; the nearest file wins. `--config PATH` uses only the named file.

Settings resolve in this order, with later layers taking precedence:

1. built-in defaults;
2. the selected `default` or `strict` profile;
3. configuration-file values;
4. explicit CLI values.

The default profile leaves all native severities at their catalog defaults. The
strict profile promotes `UX002` from `info` to `warning`. A configuration rule
override is applied after the profile and can therefore override that promotion.

## File format

```toml
profile = "strict"

[lint]
fail_on = "warning"       # error | warning | info
format = "json"           # text | json | sarif

[rules]
UX001 = "error"           # error | warning | info | off
UX002 = "warning"

[select]
include = ["PX", "UX"]
ignore = ["UX002"]
```

Only native-rule severity is configurable. `PX001`–`PX006` and `PX999` remain
fixed semantic errors because pyxform is the semantic authority. Unknown keys,
profiles, formats, severities, rule IDs, and selectors are configuration errors
and exit with status 2.

## Selection

`--select RULES` and `--ignore RULES` replace the corresponding configured list
independently. Values are comma-separated exact rule IDs or category prefixes:
`PX`, `CHO`, `LBL`, `I18N`, `UX`, and `ORD`. Configuration uses arrays of the
same selectors. Glob syntax is not supported. Ignore wins over include.

Selection controls reporting. Suppressing a fatal PX diagnostic does not erase
the semantic failure: the diagnostic can be hidden while the process still
exits 1.

## Failure threshold and output

`--fail-on error|warning|info` sets the minimum visible severity that exits 1.
The default is `error`. `--format text|json|sarif` selects output; the default is
`text`. Expected input, configuration, and usage failures exit 2. Unexpected
internal linter failures exit 3.
