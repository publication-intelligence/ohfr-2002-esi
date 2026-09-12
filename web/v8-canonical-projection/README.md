# V8 canonical web projection

This directory is the deterministic, public-safe data source for rebuilding the customer-facing evaluation page. The completed V8 result remains authoritative; this package adds the complete display collections and a separately identified representation-adjusted view.

## View policy

- `canonical_as_delivered` is the authoritative and primary observation. Its percentage-native score is 89.38/100.
- `representation_adjusted` is the default display view. It repairs only the 14 confirmed digit-for-accent headings and their demonstrated downstream consequences.
- The adjusted display retains the canonical 89.38/100 score and an explicit zero delta. The percentage-native report scores the as-delivered evidence; confirmed representation corrections are presentation-only and do not create a separate scoring view.
- `XREF-9A63B6DC42BB` resolves after `lev2e en masse` becomes `levée en masse`. `XREF-6E6F54660707` remains unresolved, so the cross-reference gate remains triggered and the result remains not publication ready.

## Files

- `projection.v1.json` — view selection, both scorecards, gates/readiness, correction outcomes, item summaries, provenance, and collection bindings.
- `data/correction-overlay.v1.json` — all 14 affected node/path/record IDs, complete delivered and corrected heading paths, all 18 character substitutions, causal classifications, and adjusted item outcomes.
- `data/index-records.v1.json` — all 1,904 records in delivered order, full hierarchy, displayed and atomic locator mappings, page labels, cross-references, and item assessments/popovers.
- `data/source-subjects.v1.json` — all 638 source-subject assessments and reader tasks, with 1,569 expected-treatment page records.
- `data/density.v1.json` — all 17 named chapter/intellectual-unit measurements and canonical fit judgments.
- `projection.schema.json` and `collection.schema.json` — Draft 2020-12 validation contracts.

Every generated JSON artifact has a canonical-JSON self-hash. `projection.v1.json` also records the byte hash of each collection and all source-artifact hashes used for the projection.

## Regenerate

The complete V8 evaluation inputs must be available under the ignored `staging/v8/evaluation/` tree. The builder verifies their hashes against the committed V8 result before using them.

```bash
python3 scripts/build_v8_web_projection.py build
```

To validate committed output without rebuilding:

```bash
python3 scripts/build_v8_web_projection.py validate
python3 -m unittest tests.test_v8_web_projection -v
git diff --check
```

## Public-safety boundary

The generated projection contains no source excerpts, PDFs, private layout evidence, absolute paths, or restricted files. Restricted detailed artifacts are local build inputs only; the projection retains their logical identities and hashes without publishing the source files themselves.

The representation-adjusted view is a display counterfactual bound to the canonical V8 evaluation. It does not overwrite the as-delivered result and does not reconstruct aggregate scores by averaging diagnostic item grades.
