# Published Oxford index — targeted V8.1 migration

The revised result is **89.38/100**, unchanged from V8. Publication gates fall from **four to zero**. Evaluation validity is **valid**, with no blockers. All ordinary numeric deductions and diagnostic item assessments remain unchanged.

This is the explicitly authorized consequence-policy migration to methodology commit `25fa3983f4980ad6a168610e08b128def11258b2`. It uses `subject-index-standard-policy-v8.1`, `subject-index-rubric-v8.1`, and `subject-index-dimension-calculation-v6`. Compatible schema filenames retain their previous versions.

## Scores and ceilings

| Dimension | Ordinary percentage | Final percentage, V8 and V8.1 | V8.1 ceiling |
| --- | ---: | ---: | --- |
| Meaningful Coverage | 86.925926 | 86.925926 | 90%, non-binding |
| Editorial Selectivity | 76.826575 | 76.826575 | None |
| Conceptual/Stance Fidelity | 99.086134 | 99.086134 | None |
| Page-reference Reliability | 93.090124 | 90 | 90%, binding |
| Findability/Navigation | 90.589021 | 90.589021 | None |
| Mechanics/Consistency | 99.855567 | 99.855567 | None |

Coverage's non-binding ceiling comes from four missing essential benchmark subjects out of 178 (2.2472%): `SUBJ-0190`, `SUBJ-0191`, `SUBJ-0219`, and `SUBJ-0250`. The frozen quantitative essential-miss band is above zero through 5%; its ceiling exceeds the ordinary score. The raw missing-access rows do not supply a separately structured central-omission defect with the required severity basis and retrieval consequence; absent headings or treatments alone do not establish an additional publication gate.

Reliability's binding ceiling comes from **93/5,338 unsupported severe/no-fit delivered locators (1.7422%) across 16/17 source units (94.1176%)**. This exceeds the minimum three items, 1% item rate, and 25% source-unit spread, landing in the 1%–below-3% band. V8 counted 94 items. `LOC-F2F22AD0F6EB` has `material_mismatch`, not severe mismatch/no fit, so V8.1 excludes it from this ceiling population while retaining its unsupported judgment and ordinary deduction. The ceiling remains 90%. All 93 IDs, counts, thresholds, and consequences appear in the ledger and the report tooltip.

High-value treatment recall retains its numeric diagnostic value; its weight labels change from `cap_only` to `reported_diagnostic_only`. No pooled treatment-recall ceiling is applied. All 102 material-partial-fit locators remain yellow review signals, and supplemental-route findings retain their diagnostic grades.

## Publication gate decisions

| Old gate | Frozen defect | V8.1 decision |
| --- | --- | --- |
| Stance | `DEFECT-STRUCT-RELATIONSHIP-001` | Minor, repairable relationship friction with `slows`; no major/critical blocking or misleading consequence. |
| Compound | Same defect | CMP code alone and ordinary partial-fit evidence cannot establish a gate; no qualifying delivered severe/no-fit locator is attached to this defect. |
| Cross-reference | `DEFECT-STRUCT-XREF-001` | Two minor references/16 (12.5%) fail the ten-item minimum; 2/1,066 structural sections (0.1876%) fail 25% spread. |
| Clutter | `DEFECT-STRUCT-SUBDIVISION-001` | Three paths/1,904 (0.1576%) in 3/1,066 sections (0.2814%) fail the count, prevalence, and spread requirements. |

All four minor structure defects remain in the evaluation. The confirmed correction overlay still contains 14 headings and 18 character substitutions. `XREF-9A63B6DC42BB` resolves in the corrected display; `XREF-6E6F54660707` remains a minor broken supplementary route. Neither gates publication. Publication readiness is distinct from validity: uninspectability, source-span mismatch, and incomplete audit attestation are not publication gates. Current preflight finds none of those blockers and no candidate-output failure.

## Preservation and provenance

Original public V8 bytes remain unchanged in `candidate/v8/` and `web/v8-canonical-projection/`, preserved at Git commit `7da416b`. The exact private evaluation was recovered from the saved project's ignored staging directory and copied to `staging/v8.1/original/`; its full archive hash inventory is in the ledger. The current private canonical state is `staging/v8.1/evaluation/evaluation-state.json`.

All **37 exact final calculation input hashes** match. Discovery, independent candidate-blind review, benchmark content, source mapping, normalization, all 34 chunk audits, and the structure V6 judgments are reused. No approvals or new candidate-blind reviews were created. The benchmark retains its original V8 policy and release provenance. The new policy's historical top-level freeze is explicitly distinguished from the migration freeze in `policy_profile.migration`, which records that the candidate was seen during migration.

The recovered state predated the published percentage/causal artifacts: it selected structure V5 and calculation-profile V4. The migration registers the exact structure V6 bytes bound by the published result and compares against that result's calculation-profile V5. Only structure registration, scoring, and reporting were reopened and completed through the installed commands.

The current report producer emits one authoritative score view plus the complete correction overlay and four collections. The previous two-view display adapter remains preserved with the V8 bundle. No new adjusted aggregate score is claimed.

A pre-existing byte mismatch for `source/chunks/source-chunk-inventory.json` remains an explicit state warning. It is not among the 37 calculation inputs. Its original recorded and observed hashes are documented; this migration does not repair unrelated registration history.

## Artifacts and validation

- `evaluation-result.v12.json`: current result, gates, validity, and review signals.
- `web-report.v10.json`: current report with exact cap-evidence tooltips.
- `../../web/v8.1-canonical-projection/`: projection and index-record, source-subject, density, and correction-overlay collections.
- `migration-ledger.json`: old/new identities, original/changed artifact hashes, affected stable IDs, unchanged evidence, and every substantive/mechanical change.
- `../../validation/v8.1-validation-receipt.json` and `v8.1-regression-results.json`: validation results.

Passed: current schemas and full projection safety/joins/hashes; canonical state; exact original input hashes; audit semantics and causal provenance; valid preflight; exact deterministic recalculation; unchanged diagnostic item records; score arithmetic; **150 methodology tests, 19 consequence regressions, and 17 existing repository tests**. Initial attempts using incomplete Python environments failed dependency imports; complete runs passed in the methodology environment.

To validate the public artifacts with a dependency-complete Python environment:

```sh
python scripts/validate_v8_1.py --skill /path/to/evaluate-subject-index
```

Add `--private` to validate the preserved private archive and reproduce the calculation. `scripts/migrate_v8_1.py` documents the deterministic migration; rerunning it requires a pristine copy of the exact archive at `staging/v8.1/original/` and a separate working copy at `staging/v8.1/evaluation/`, with generated V8.1 outputs absent. Restricted evidence remains ignored and must accompany a private handoff separately from the public Git commit.
