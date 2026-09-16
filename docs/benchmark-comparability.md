# Benchmark comparability investigation

The four Oxford reports are **not one controlled four-way benchmark comparison**. The displayed denominator split is real and persists in the completed V8.2 migrations. All four use the same source PDF SHA-256, page map and 17 chunk boundaries, but they use two different source-benchmark contents. The V8.2 migrations remain valid changes within each frozen evaluation; they do not establish cross-benchmark score comparability.

| Evaluation family | Subjects | Expected treatments | Reader tasks | Relationships | Essential / major / optional | Source-word measurement |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| Published + IndexPDF | 638 | 1,569 | 638 | 281 | 178 / 356 / 104 | 195,346 |
| IndexerLabs + Indexia | 1,366 | 3,210 | 1,026 | 3,460 | 155 / 1,125 / 86 | 194,718 |

The subject, relationship, reader-task, exclusion and uncertainty arrays are exactly equal within each pair, despite valid differences in per-evaluation wrappers and hashes. They are different across the pairs; no stable subject IDs overlap. Every subject ID and coalesced expected-treatment identity is unique within its own benchmark. Neither family has duplicate normalized subject labels. These checks do not prove absence of semantic redundancy, but rule out the proposed literal record doubling.

The machine-readable evidence, artifact hashes, semantic-content digests and dates are in [`validation/benchmark-comparability.json`](../validation/benchmark-comparability.json). The checked website-source projections independently reproduce the same 638/1,366 counts.

## Corrected lineage

The benchmark repository's legacy v2 already contained **1,366 subjects**. Its file hash is `de16bd7bae84a5afcc9ff8b46ff1b29c9a6eb6824a592d970f9dad0bb5679cc1`. The reviewed v3 retained 1,366 subjects and was frozen on **2026-08-24**, at artifact commit [`98dbffd0ca171b5b7db76dbe1b2b5d5265ccacab`](https://github.com/publication-intelligence/ohfr-2002-esi-benchmark/commit/98dbffd0ca171b5b7db76dbe1b2b5d5265ccacab). Its canonical hash is `b925797fcab50b2008ad5974590e323f772e5ea7013efa84ce7606007439aeb3`. The historical systemic-defect stop was cleared by the final coordinator; it remains recorded as history, not an active release blocker.

The **638-subject native V8 benchmark is a separate release**, frozen on **2026-09-09**, with canonical hash `558980b374ca4b162b12f2726e237319b170f9e8b7014f71ad7c2171e9e98983`. Its own native v1 draft received independent candidate-blind review before becoming native v2. It is not the rejected legacy v2, and the evidence does not show an expansion from 638 to 1,366.

IndexPDF imported the native release with identity-only rebinding. IndexerLabs and Indexia imported the legacy v3 through reviewed compatibility imports; their benchmark content is exactly the legacy release after the permitted `type` to `relationship_type` key normalization. Later policy migrations preserved those benchmarks and their dependent audits. A shared V8.2 methodology label therefore conceals two preserved comparison baselines unless their content identity is checked separately.

The benchmark repository's reuse instructions already call for every candidate comparison to pin its immutable v3 release. That is evidence of the study's intended common lock, but the later independently reviewed native release exists too. Selection must be justified from the source, study protocol and release provenance, rather than larger counts or favorable scores. The coordinator should have checked shared benchmark identity before describing the four-way migration as ready.

## Effect on current results

Three directly benchmark-dependent dimensions carry **65% of overall weight**:

- **Meaningful Coverage (20%)** uses priority-weighted subject access. Subject boundaries, access requirements and 3/2/1 priority weights differ. Essential-miss and central-omission consequences also depend on those judgments.
- **Page-reference Reliability (25%)** combines delivered-locator keep precision with expected-treatment recall. The delivered-locator evidence can remain valid while a different treatment population changes recall and the resulting harmonic mean.
- **Findability (20%)** uses coverage-conditioned reader tasks, architecture and reference validity. Task populations, required subjects, warranted access routes, applicability and related defects can change.

This 65% is exposure to the benchmark definition, **not a measured 65-point error, a direction of bias, or proof the ranking reverses or survives**. Percentages cannot be normalized by dividing or multiplying by the subject-count ratio. The slightly different source-word measurements also affect density and should receive one declared common basis in a controlled comparison.

Selectivity, conceptual/stance fidelity, mechanics, locator support and physical cross-reference resolution contain useful reusable evidence, but benchmark-dependent route/relationship/applicability findings still require examination. The new direct wrong-locator and broken-reference gates are grounded in delivered destinations rather than the source-subject count. Their findings remain meaningful; gate aggregation and uncertainty must nevertheless be recomputed in any new registered evaluation context.

## Crosswalk preflight and economical recovery

A bounded source-benchmark matching pass produced **36 exact normalized-label seed pairs**. Fifteen also have the same coalesced evidence page/class sets; only nine also share priority. No pair has byte-identical meaning, stance and acceptable-access text. Text differences do not prove semantic differences, and different labels may still express the same requirement. These statistics establish neither the amount of reusable work nor the number of genuinely new requirements.

[`validation/benchmark-crosswalk-preflight.json`](../validation/benchmark-crosswalk-preflight.json) preserves those unapproved seed pairs. It is not an adjudicated crosswalk or permission to transfer judgments. The matching did not use candidate outcomes, but the coordinator has seen candidates; no new candidate-blind review is claimed.

Before paying for broad reruns:

1. Confirm one common source-benchmark release, using the study's existing lock and source-led quality/provenance criteria. If source requirements must be reconciled semantically, version and independently review that reconciliation in a genuinely candidate-unexposed context. Preserve both historical releases and disclose retrospective selection.
2. Crosswalk subject meaning, scope, stance, acceptable access, priorities, reader tasks and coalesced subject/page/locator-class treatments. Distinguish equivalents, splits, merges, changed requirements, unmapped requirements and ambiguity. Source-page overlap alone is insufficient.
3. Approve reuse only where the existing evidence actually answers the same requirement. Reuse unchanged source/candidate normalization, delivered-locator support, layout and independent structure evidence. Rebuild missing-access worksets and review changed or new obligations, plus their dependent task/architecture/defect findings. An existing broad-subject judgment cannot automatically be copied to all narrower subjects.
4. Recompute scores, caps, gates and reports on the common benchmark. Score/cap invariance is required for today's policy-only migration but is **not expected or enforced** across a substantive benchmark change.
5. Add a study/importer comparison guard for source scope, benchmark semantic content/release lineage, methodology, population/applicability and density basis. Different per-evaluation wrapper hashes may be legitimate; a common methodology version or matching counts alone is insufficient.

A reviewed crosswalk may support bounded supplemental missing-access and related review instead of an entire restart. The present data does not establish that most work can be transferred mechanically. Completed candidate-exposed states must not have visibility flags reset or old audit IDs relabeled to bypass the supported review/import workflow.

## Coordination disposition

Keep the completed individual V8.2 migrations and their verified archives. Keep the four evaluation PRs in draft and hold merges, saved-project activation, four-way comparative claims and website bundle cutover until a common-benchmark plan is approved. No benchmark has been replaced, no audit rerun has begun, and no individual evaluation-validity flag has been changed by this investigation.
