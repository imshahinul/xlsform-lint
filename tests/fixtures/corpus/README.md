# Phase 2 XLSForm regression corpus

This bounded corpus contains synthetic, minimized XLSForms for regression and
oracle testing. It contains no real identifiers, participant data, private
study instruments, or copyright-restricted third-party forms. All fixtures may
be redistributed under the repository's Apache-2.0 license.

[`manifest.json`](manifest.json) is the machine-readable fixture inventory and
oracle. Each entry records its category, purpose, constructs, pyxform
acceptance expectation, clean status, and exact expected public rule IDs.

## Categories

| Category | Meaning |
| --- | --- |
| `valid` | Legitimate XLSForms expected to be accepted by pyxform and produce no findings. |
| `findings` | Deliberate, narrowly specified existing diagnostics. |
| `malformed` | Isolated structural or semantic failures for failure-path regression. |

## Construct coverage

| Construct | Fixture(s) |
| --- | --- |
| Basic form | `valid/basic_clean.xlsx` |
| Groups / nested groups | `valid/nested_groups.xlsx`, `valid/complex_combined.xlsx` |
| Repeats / group-repeat interaction | `valid/repeat_interaction.xlsx`, `valid/complex_combined.xlsx` |
| `select_one` / `select_multiple` / multiple lists | `valid/selects_and_filter.xlsx`, `valid/complex_combined.xlsx` |
| Earlier-field `choice_filter` | `valid/selects_and_filter.xlsx`, `valid/complex_combined.xlsx` |
| Translations / multiple label languages | `valid/multilingual_constraints.xlsx`, `valid/complex_combined.xlsx` |
| Constraints / constraint messages | `valid/repeat_interaction.xlsx`, `valid/multilingual_constraints.xlsx` |
| Relevance / calculations | `valid/logic_and_internal.xlsx`, `valid/complex_combined.xlsx` |
| Notes / hidden fields | `valid/logic_and_internal.xlsx` |
| Required / defaults | `valid/required_and_defaults.xlsx`, `valid/complex_combined.xlsx` |
| Large static choice list | `valid/large_choice_list.xlsx` (250 synthetic choices) |
| Mixed legitimate constructs | `valid/complex_combined.xlsx` |
| Mixed intentional findings | `findings/mixed_native_findings.xlsx` |
| Semantic / malformed failure | `malformed/unknown_choice_list.xlsx`, `malformed/unmatched_end_group.xlsx` |

## Native-rule coverage baseline

| Rule | Positive corpus | Negative clean corpus | Existing dedicated unit coverage |
| --- | --- | --- | --- |
| CHO001 | `findings/mixed_native_findings.xlsx` | all valid forms with choices | `test_cho001_matrix` |
| LBL001 | `findings/mixed_native_findings.xlsx` | all valid visible/note labels | `test_lbl001_type_and_translation_matrix` |
| LBL002 | `findings/mixed_native_findings.xlsx` | all valid choice labels | `test_lbl002_and_choice_i18n_noise_matrix` |
| I18N001 | `findings/mixed_native_findings.xlsx` | multilingual valid forms | `test_i18n001_survey_matrix` |
| UX001 | `findings/mixed_native_findings.xlsx` | valid constrained forms | `test_ux001_matrix` |
| ORD001 | `findings/mixed_native_findings.xlsx` | valid earlier-field filters | `test_ord001_is_choice_filter_only_and_unambiguous` |
| UX002 | `findings/mixed_native_findings.xlsx` | `valid/required_and_defaults.xlsx` | `test_ux002_matrix_and_severity` |

## Reproduction

Run `python3 tests/fixtures/corpus/generate_corpus.py` from the repository root.
The script is deliberately small and uses only the pinned openpyxl dependency.
XLSX ZIP metadata can vary by generation time; corpus tests compare workbook
content and oracles rather than byte-level ZIP identity.
