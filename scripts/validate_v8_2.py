#!/usr/bin/env python3
"""Validate the V8.2 public bundle and, optionally, exact private evidence reuse."""
import argparse
import copy
from pathlib import Path
import sys
from migrate_v8_1 import ROOT, read, sha, write
from migrate_v8_2 import BASE, TARGET, PUBLIC, RELEASE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skill', type=Path, required=True)
    parser.add_argument('--private', action='store_true')
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.skill / 'scripts'))
    import dimension_score_v8_cli as scoring
    import scoring_core as core
    import web_projection
    from state_cli import validate_state
    ledger = read(PUBLIC / 'migration-ledger.json')
    result = read(PUBLIC / 'evaluation-result.v12.json')
    report = read(PUBLIC / 'web-report.v10.json')
    folder = ROOT / 'web/v8.2-canonical-projection'
    projection = read(folder / 'projection.v1.json')
    for name, data in [('evaluation-result-v12.schema.json', result), ('web-report-v10.schema.json', report)]:
        core.validate_schema_document(data, name, name)
    collections = {r['collection_id']: read(folder / r['artifact_path']) for r in projection['collections']}
    web_projection.validate_bundle(projection, collections)
    for r in ledger['public_artifact_hashes']:
        assert sha(ROOT / r['path']) == r['sha256'], r['path']
    assert result['overall_percentage'] == ledger['score_comparison']['original'] == ledger['score_comparison']['revised']
    assert result['scorecard'] == report['scorecard']
    gates = {g['gate_id']: g for g in result['critical_gates'] if g['triggered']}
    assert set(gates) == {'GATE-WRONG-LOCATOR', 'GATE-BROKEN-REFERENCE'}
    assert gates['GATE-BROKEN-REFERENCE']['affected_evidence_ids'] == ['XREF-6E6F54660707']
    assert result['evaluation_validity'] == read(ROOT / 'candidate/v8.1/evaluation-result.v12.json')['evaluation_validity']
    assert projection['score_views']['views'][0]['readiness']['status'] == 'not_publication_ready'
    assert collections['correction_overlay']['affected_heading_count'] == 14
    assert collections['correction_overlay']['cross_reference_resolution']['cross_reference_gate_triggered_after_correction'] is True
    assert result['gate_assessment'] == report['gate_assessment'] == ledger['gate_assessment']
    checks = ['result/report schemas', 'complete bundle hashes, joins and public safety', 'unchanged score and validity', 'direct gate and readiness parity', 'confirmed correction overlay preserved']
    warnings, state_hash = [], None
    if args.private:
        for r in ledger['baseline_archive_inventory']:
            assert sha(BASE / r['path']) == r['sha256'], r['path']
        old = read(BASE / 'scoring/v8.1/dimension-calculations.v6.json')
        new = read(TARGET / 'scoring/v8.2/dimension-calculations.v6.json')
        for before, after in zip(old['dimensions'], new['dimensions'], strict=True):
            assert {k: v for k, v in before.items() if k not in ('formula_id', 'input_artifacts')} == {k: v for k, v in after.items() if k not in ('formula_id', 'input_artifacts')}
        for ref in old['input_artifacts']:
            path = (BASE / 'scoring/v8.1' / ref['path']).resolve()
            assert sha(path) == ref['sha256']
            assert sha(TARGET / path.relative_to(BASE)) == ref['sha256'], ref['role']
        state = read(TARGET / 'evaluation-state.json')
        errors, warnings = validate_state(state, state_path=TARGET / 'evaluation-state.json')
        assert not errors, errors
        assert all(s['status'] == 'completed' for s in state['stages'].values())
        assert read(TARGET / 'migration/migration-ledger.v8.2.json') == ledger
        policy = read(TARGET / 'source/evaluation-policy.v8.2.json')
        scoring.validate_v8_policy(policy)
        assert policy['freeze']['candidate_seen'] is True
        original = read(BASE / 'source/evaluation-policy.v4.json')
        assert policy['retrospective_migration']['original_policy']['freeze'] == original['freeze']
        assert original['freeze']['candidate_seen'] is False
        assert 'migration' not in policy['policy_profile']
        inp = read(TARGET / 'migration/policy-build-input.v8.2.json')
        assert inp['retrospective_migration'] == policy['retrospective_migration']
        for stage in inp['retrospective_migration']['reused_stages'].values():
            for ref in stage['evidence']:
                assert sha(TARGET / 'migration' / ref['path']) == ref['sha256']
        loaded = scoring.load_v8_inputs((TARGET / 'scoring/v8.2/dimension-calculation-input.v2.json').resolve())
        _, missing = scoring.preflight_loaded(loaded)
        assert not missing, missing
        assert core.json_output_value(scoring.calculate_loaded(loaded)) == new
        before_items = read(BASE / 'scoring/v8.1/item-assessments.v7.json')
        after_items = read(TARGET / 'scoring/v8.2/item-assessments.v7.json')
        assert {k: v for k, v in before_items.items() if k != 'evidence_identity'} == {k: v for k, v in after_items.items() if k != 'evidence_identity'}
        structure = read(TARGET / 'structure/structure-audit.v8.2.v6.json')
        stripped = copy.deepcopy(structure)
        for row in stripped['cross_reference_judgments']:
            row.pop('target_resolution')
        assert stripped == read(BASE / 'structure/structure-audit.v6.json')
        # Every direct locator gate is traceable to an unchanged finalized audit row.
        rows = {r['locator_id']: r for p in TARGET.glob('candidates/*/locator-audits/*.json') for r in read(p).get('judgments', [])}
        for item in gates['GATE-WRONG-LOCATOR']['direct_destination_evidence']:
            audit = rows[item['locator_id']]
            assert all(audit[k] == v for k, v in item.items())
            assert audit['judgment'] == 'unsupported' and audit['complete_path_fit'] == 'no_fit'
        for field in ('dimension_calculations', 'item_assessments', 'structure_audit', 'projection_metadata'):
            assert sha(TARGET / result[field]['artifact_path']) == result[field]['sha256']
        for ref in projection['provenance']['source_artifacts']:
            assert sha(TARGET / ref['artifact_path']) == ref['sha256']
        state_hash = sha(TARGET / 'evaluation-state.json')
        checks += ['exact frozen baseline archive', 'all original calculation input bytes preserved', 'all numeric components and caps invariant', 'canonical state and completed stages', 'native retrospective provenance', 'deterministic calculation reproduction', 'unchanged diagnostic items and structure judgments', 'direct gate evidence traced to original audit rows', 'private report/projection provenance bindings']
    receipt = {'schema_version': 'ohfr-targeted-v8.2-validation-receipt-v1', 'ok': True, 'methodology_commit': RELEASE, 'ledger_sha256': sha(PUBLIC / 'migration-ledger.json'), 'canonical_state_sha256': state_hash, 'checks': checks, 'warnings': warnings}
    if args.receipt:
        write(args.receipt, receipt)
    print(receipt)


if __name__ == '__main__':
    main()
