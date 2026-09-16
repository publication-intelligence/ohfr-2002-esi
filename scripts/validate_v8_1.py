#!/usr/bin/env python3
"""Validate the targeted migration's public bundle and exact private evidence reuse."""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import sys

from migrate_v8_1 import ROOT, read, sha, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skill', type=Path, required=True)
    parser.add_argument('--private', action='store_true', help='Also validate archived inputs and reproduce the calculation.')
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.skill / 'scripts'))
    import dimension_score_v8_cli as scoring
    import scoring_core as core
    import web_projection
    from state_cli import validate_state

    ledger = read(ROOT / 'candidate/v8.1/migration-ledger.json')
    result = read(ROOT / 'candidate/v8.1/evaluation-result.v12.json')
    report = read(ROOT / 'candidate/v8.1/web-report.v10.json')
    projection = read(ROOT / 'web/v8.1-canonical-projection/projection.v1.json')
    for name, value in [('evaluation-result-v12.schema.json', result), ('web-report-v10.schema.json', report)]:
        core.validate_schema_document(value, name, name)
    collections = {b['collection_id']: read(ROOT / 'web/v8.1-canonical-projection' / b['artifact_path']) for b in projection['collections']}
    web_projection.validate_bundle(projection, collections)
    for record in ledger['public_artifact_hashes']:
        assert sha(ROOT / record['path']) == record['sha256'], record['path']
    assert result['overall_percentage'] == ledger['score_comparison']['revised']
    assert result['scorecard'] == report['scorecard']
    assert all(not g['triggered'] for g in result['critical_gates'])
    assert result['evaluation_validity'] == {'status': 'valid', 'blockers': [], 'used_as_publication_gate': False}
    assert projection['score_views']['views'][0]['readiness']['status'] == 'publication_ready'
    assert collections['correction_overlay']['affected_heading_count'] == 14
    assert collections['correction_overlay']['cross_reference_resolution']['cross_reference_gate_triggered_after_correction'] is False
    partial = next(s for s in result['review_signals'] if s['signal_id'] == 'REVIEW-PARTIAL-FIT')
    assert partial['color'] == 'yellow' and len(partial['affected_evidence_ids']) == 102
    # Every displayed ceiling must expose the exact selected calculation record.
    displayed = []
    for dimension in report['presentation_summary']['dimensions']:
        for line in dimension['calculation_basis']:
            if 'ceiling' in line['equation'].lower() or 'applied cap' in line['equation'].lower():
                cap = json.loads(line['tooltip'])
                assert cap['triggered'] and cap['affected_evidence_ids']
                assert all(cap['observed'][key] for key in ('severity_basis', 'retrieval_consequence', 'threshold_reason'))
                displayed.append(cap['cap_id'])
    expected = [c['cap_id'] for d in ledger['dimension_comparison'] for c in d['revised_triggered_ceilings']]
    assert sorted(displayed) == sorted(expected)
    assert any('Non-binding triggered ceiling' in row['equation'] for row in report['presentation_summary']['dimensions'][0]['calculation_basis'])
    state_hash = None
    checks = ['current result/report schemas', 'complete public bundle schemas, self-hashes, joins and safety', 'public artifact byte hashes', 'scorecard and readiness parity', 'correction overlay facts and revised minor-gate consequence', '102 yellow partial-fit signals', 'complete ceiling tooltips and non-binding label']
    warnings = []
    if args.private:
        original = ROOT / 'staging/v8.1/original'
        target = ROOT / 'staging/v8.1/evaluation'
        for row in ledger['original_archive_inventory']:
            assert sha(original / row['path']) == row['sha256'], row['path']
        for row in ledger['exact_original_calculation_inputs']:
            assert sha(original / row['path']) == row['sha256']
            # No source/audit ledger bytes were edited during this migration.
            assert sha(target / row['path']) == row['sha256']
        state_hash = sha(target / 'evaluation-state.json')
        state = read(target / 'evaluation-state.json')
        assert read(target / 'migration/migration-ledger.json') == ledger
        errors, warnings = validate_state(state, state_path=target / 'evaluation-state.json')
        assert not errors, errors
        assert all(stage['status'] == 'completed' for stage in state['stages'].values())
        loaded = scoring.load_v8_inputs((target / 'scoring/v8.1/dimension-calculation-input.v2.json').resolve())
        _, missing = scoring.preflight_loaded(loaded)
        assert not missing, missing
        calculation = read(target / 'scoring/v8.1/dimension-calculations.v6.json')
        reproduced = core.json_output_value(scoring.calculate_loaded(loaded))
        assert reproduced == calculation, 'Calculation did not reproduce exactly'
        original_items = read(original / 'scoring/causal-percentage-native/item-assessments.v7.json')
        current_items = read(target / 'scoring/v8.1/item-assessments.v7.json')
        assert {k: v for k, v in original_items.items() if k != 'evidence_identity'} == {k: v for k, v in current_items.items() if k != 'evidence_identity'}
        for field in ('dimension_calculations', 'item_assessments', 'structure_audit', 'projection_metadata'):
            assert sha(target / result[field]['artifact_path']) == result[field]['sha256']
        for row in projection['provenance']['source_artifacts']:
            assert sha(target / row['artifact_path']) == row['sha256'], row
        assert sum(Decimal(d['weighted_contribution']) for d in calculation['dimensions']).quantize(Decimal('.01')) == Decimal(str(result['overall_percentage']))
        checks += ['original archive preservation', '37 exact original calculation inputs and unchanged audit bytes', 'canonical state and completed registered stages', 'current preflight validity', 'exact deterministic calculation reproduction', 'all diagnostic item records unchanged', 'result and full projection private provenance bindings', 'weighted arithmetic']
    receipt = {'schema_version': 'ohfr-targeted-v8.1-validation-receipt-v1', 'ok': True, 'current_canonical_state_sha256': state_hash, 'checks': checks, 'warnings': warnings, 'ledger_sha256': sha(ROOT / 'candidate/v8.1/migration-ledger.json'), 'methodology_commit': ledger['methodology_commit'], 'regression_results': {'path': 'validation/v8.1-regression-results.json', 'sha256': sha(ROOT / 'validation/v8.1-regression-results.json'), 'runs': read(ROOT / 'validation/v8.1-regression-results.json')['runs']}, 'runtime_note': 'Dependency-complete methodology validation environment used. Earlier system/bundled Python attempts failed dependency imports; complete reruns passed.'}
    if args.receipt:
        write(args.receipt, receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
