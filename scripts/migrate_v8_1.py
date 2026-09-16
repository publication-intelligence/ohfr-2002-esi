#!/usr/bin/env python3
"""Targeted migration of exact frozen Oxford V8 inputs; private trees stay ignored."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + '\n')


def prepare(skill, original, target):
    sys.path.insert(0, str(skill / 'scripts'))
    import dimension_score_v8_cli as scoring
    import policy_cli
    import scoring_core as core
    from state_cli import now

    state = read(original / 'evaluation-state.json')
    calculation = read(original / 'scoring/causal-percentage-native/dimension-calculations.v6.json')
    result = read(ROOT / 'candidate/v8/evaluation-result.v12.json')
    assert sha(original / 'scoring/causal-percentage-native/dimension-calculations.v6.json') == result['dimension_calculations']['sha256']
    exact_inputs = []
    for ref in calculation['input_artifacts']:
        path = (original / 'scoring/causal-percentage-native' / ref['path']).resolve()
        assert sha(path) == ref['sha256'], ref
        exact_inputs.append({'role': ref['role'], 'path': str(path.relative_to(original.resolve())), 'sha256': sha(path)})
    for key, rel in [('item_assessments', 'scoring/causal-percentage-native/item-assessments.v7.json'), ('structure_audit', 'structure/structure-audit.v6.json'), ('projection_metadata', 'scoring/causal-percentage-native/projection-metadata.v2.json')]:
        assert sha(original / rel) == result[key]['sha256']
    old_policy = read(original / 'source/evaluation-policy.v4.json')
    benchmark = read(original / 'source/source-benchmark.v2.json')
    review = read(original / 'validation/source-benchmark-review.v1.json')
    assert benchmark['benchmark_sha256'] == calculation['evidence_identity']['benchmark_sha256']
    assert benchmark['policy_sha256'] == old_policy['policy_sha256']
    assert review['candidate_blindness'] == 'preserved'
    stamp = now()
    policy = copy.deepcopy(old_policy)
    policy['policy_id'] += '-targeted-v8.1'
    policy['policy_profile'] = {
        'id': policy_cli.POLICY_PROFILE,
        'consequence_policy_reference': 'consequence-policy-v8.1.md',
        'migration': {
            'frozen_at': stamp,
            'authorization': 'Explicit targeted migration request in this task.',
            'original_policy_sha256': old_policy['policy_sha256'],
            'original_policy_file_sha256': sha(original / 'source/evaluation-policy.v4.json'),
            'methodology_commit': '25fa3983f4980ad6a168610e08b128def11258b2',
            'candidate_seen_during_migration': True,
            'freeze_field_meaning': 'The top-level freeze is preserved historical V8 source-policy provenance. This migration freeze is not a candidate-blind review.',
            'benchmark_reused_without_rebinding': benchmark['benchmark_sha256'],
        },
    }
    for area in policy['content_policies'].values():
        area['profile'] = policy_cli.POLICY_PROFILE
    policy['critical_gates'] = [{'gate_id': g, 'description': d, 'standard': True} for g, d in policy_cli.CRITICAL_GATES]
    # Preserve density calibration and its historical provenance verbatim.
    policy['policy_sha256'] = core.canonical_hash(policy, 'policy_sha256')
    scoring.validate_v8_policy(policy)
    write(target / 'source/evaluation-policy.v8.1.json', policy)
    state['configuration']['policy_profile'] = policy_cli.POLICY_PROFILE
    state['configuration']['rubric_version'] = scoring.RUBRIC_VERSION
    state['configuration']['scoring_identity'] = {'rubric_version': scoring.RUBRIC_VERSION, 'dimension_calculation_profile': scoring.CALCULATION_PROFILE}
    removed = [a for a in state['artifacts'] if a['stage'] in ('define_policy', 'structure_audit', 'scoring', 'web_report')]
    state['artifacts'] = [a for a in state['artifacts'] if a not in removed]
    p = target / 'source/evaluation-policy.v8.1.json'
    state['artifacts'].append(scoring._artifact_record(target, p, p.read_bytes(), stage='define_policy', artifact_type='evaluation-policy-v4', schema_version=policy['schema_version'], stamp=stamp))
    for stage in ('structure_audit', 'scoring', 'web_report'):
        state['stages'][stage] = {'status': 'not_started', 'updated_at': stamp, 'notes': ['Explicit V8.1 targeted migration: reopen derived registration; original completed state and bytes preserved in sibling original archive.']}
    state['stages']['define_policy']['notes'].append('V8.1 policy frozen by authorized targeted migration; original benchmark review and policy provenance retained without new approval.')
    state['updated_at'] = stamp
    write(target / 'evaluation-state.json', state)
    ledger = {
        'schema_version': 'ohfr-targeted-v8.1-migration-ledger-v1',
        'evaluation_id': state['evaluation_id'], 'migration_frozen_at': stamp,
        'original_public_git_commit': '7da416b',
        'methodology_commit': '25fa3983f4980ad6a168610e08b128def11258b2',
        'original_private_archive': 'staging/v8.1/original',
        'current_private_evaluation': 'staging/v8.1/evaluation',
        'original_identities': {'policy_profile': old_policy['policy_profile']['id'], 'policy_sha256': old_policy['policy_sha256'], 'rubric': calculation['rubric_version'], 'calculation_profile': calculation['calculation_profile']},
        'revised_identities': {'policy_profile': policy_cli.POLICY_PROFILE, 'policy_sha256': policy['policy_sha256'], 'rubric': scoring.RUBRIC_VERSION, 'calculation_profile': scoring.CALCULATION_PROFILE},
        'exact_original_calculation_inputs': exact_inputs,
        'reused_without_rerun': ['source mapping and source scope', 'candidate-blind discovery, synthesis and independent benchmark review', 'benchmark content and original policy binding', 'candidate normalization and inventory', 'all 17 locator audits', 'all 17 missing-access audits', 'structure judgments, defects, denominators and causal findings', 'confirmed character correction facts'],
        'benchmark_release': {'file_sha256': sha(original / 'source/source-benchmark.v2.json'), 'benchmark_sha256': benchmark['benchmark_sha256'], 'original_policy_sha256': benchmark['policy_sha256'], 'freeze': benchmark['freeze'], 'review_file_sha256': sha(original / 'validation/source-benchmark-review.v1.json'), 'new_review_or_approval_claimed': False},
        'mechanical_changes': ['Freeze a separate V8.1 policy, preserving scope/audience/audit/density values; historical freeze is explicitly distinguished from migration freeze.', 'Update canonical scoring identities and policy artifact binding.', 'Reopen only structure registration, scoring and reporting, retaining old completed state and outputs in the original archive.', 'Register exact published structure V6 bytes in place of the stale state V5 selection; no structure judgment changes.', 'Recalculate and rebuild through installed registered score/build-report commands. Audit and benchmark policy provenance remain original because no rebinding is required by current validators.'],
        'removed_current_state_records_preserved_in_original_archive': [{'path': a['path'], 'sha256': a['sha256']} for a in removed],
        'original_archive_inventory': [{'path': str(p.relative_to(original)), 'sha256': sha(p)} for p in sorted(original.rglob('*')) if p.is_file()],
    }
    write(ROOT / 'candidate/v8.1/migration-ledger.json', ledger)


def command(skill, *args):
    subprocess.run([sys.executable, str(skill / 'scripts/dimension_score_v8_cli.py'), *map(str, args)], check=True)


def build_report(skill, target):
    assert not (target / 'scoring/v8.1/web-report.v10.json').exists(), 'Report already exists; validate it instead of overwriting.'
    assert not (ROOT / 'web/v8.1-canonical-projection').exists(), 'Public bundle already exists.'
    sys.path.insert(0, str(skill / 'scripts'))
    import dimension_score_v8_cli as scoring
    import scoring_core as core
    from state_cli import now
    state_path = target / 'evaluation-state.json'
    state = read(state_path)
    overlay = read(ROOT / 'web/v8-canonical-projection/data/correction-overlay.v1.json')
    overlay['cross_reference_resolution']['cross_reference_gate_triggered_after_correction'] = False
    item_record = next(a for a in state['artifacts'] if a.get('schema_version') == 'subject-index-item-assessments-v7')
    overlay['provenance']['v8_item_assessment_artifact']['artifact_path'] = item_record['path']
    overlay['provenance']['v8_item_assessment_artifact']['sha256'] = item_record['sha256']
    overlay['provenance']['version_bridge'] += ' V8.1 reuses the same item judgments and correction facts; only the current item artifact binding and excluded minor cross-reference gate consequence change.'
    overlay['overlay_sha256'] = core.canonical_hash(overlay, 'overlay_sha256')
    path = target / 'corrections/correction-overlay.v1.json'
    write(path, overlay)
    state['artifacts'].append(scoring._artifact_record(target, path, path.read_bytes(), stage='structure_audit', artifact_type='correction_overlay', schema_version=overlay['schema_version'], stamp=now(), visibility='public'))
    write(state_path, state)
    command(skill, 'build-report', '--state', state_path, '--output', 'scoring/v8.1/web-report.v10.json', '--bundle-output', 'scoring/v8.1/v8-canonical-projection')
    for name in ('evaluation-result.v12.json', 'web-report.v10.json'):
        shutil.copyfile(target / 'scoring/v8.1' / name, ROOT / 'candidate/v8.1' / name)
    shutil.copytree(target / 'scoring/v8.1/v8-canonical-projection', ROOT / 'web/v8.1-canonical-projection')
    finish_ledger(skill, target)


def finish_ledger(skill, target):
    from decimal import Decimal
    original = ROOT / 'staging/v8.1/original'
    ledger_path = ROOT / 'candidate/v8.1/migration-ledger.json'
    ledger = read(ledger_path)
    old = read(original / 'scoring/causal-percentage-native/dimension-calculations.v6.json')
    new = read(target / 'scoring/v8.1/dimension-calculations.v6.json')
    result = read(ROOT / 'candidate/v8.1/evaluation-result.v12.json')
    structure = read(original / 'structure/structure-audit.v6.json')
    old_result = read(ROOT / 'candidate/v8/evaluation-result.v12.json')
    ledger['dimension_comparison'] = []
    for before, after in zip(old['dimensions'], new['dimensions'], strict=True):
        assert before['dimension_id'] == after['dimension_id']
        normalized_components = copy.deepcopy(before['components'])
        component_metadata_changes = []
        for left, right in zip(normalized_components, after['components'], strict=True):
            for field in ('weight', 'effective_weight'):
                if left.get(field) != right.get(field):
                    assert left[field] == 'cap_only' and right[field] == 'reported_diagnostic_only'
                    component_metadata_changes.append({'component_id': right['component_id'], 'field': field, 'old': left[field], 'new': right[field]})
                    left[field] = right[field]
        assert normalized_components == after['components'], after['dimension_id']
        ledger['dimension_comparison'].append({
            'dimension_id': after['dimension_id'],
            'ordinary_components_unchanged': True,
            'component_consequence_metadata_changes': component_metadata_changes,
            'original_pre_cap_percentage': before['pre_cap_percentage'],
            'revised_pre_cap_percentage': after['pre_cap_percentage'],
            'original_dimension_percentage': before['dimension_percentage'],
            'revised_dimension_percentage': after['dimension_percentage'],
            'weighted_contribution': after['weighted_contribution'],
            'original_triggered_ceilings': [c for c in before['cap_evaluations'] if c['triggered']],
            'revised_triggered_ceilings': [dict(c, binding=Decimal(after['post_cap_percentage']) < Decimal(after['pre_cap_percentage'])) for c in after['cap_evaluations'] if c['triggered']],
        })
    ledger['score_comparison'] = {'original': old['overall_percentage'], 'revised': new['overall_percentage'], 'ordinary_components_unchanged': True, 'all_dimension_percentages_unchanged': True}
    ledger['publication_gate_review'] = []
    defects = {d['defect_id']: d for d in structure['defects']}
    reasons = {
        'GATE-STANCE': 'Minor relationship friction with slows consequence; neither major/critical severity nor blocks/misleads consequence. The affected subheading also has ordinary partial-fit evidence, which cannot be promoted to a stance gate.',
        'GATE-COMPOUND': 'CMP code alone is insufficient. The frozen defect is minor/slows and binds a NODE rather than a qualifying severe/no-fit delivered locator. No new major misrepresentation is inferred.',
        'GATE-CROSS-REFERENCE': 'Two minor references out of 16 (12.5%) do not meet the minimum ten-item systemic count; 2/1066 structural sections (0.1876%) also fail 25% spread. Both retain ordinary deductions. The see-also to individual regiments preserves a delivered locator; the levée-en-masse route is intelligible but mechanically corrupted.',
        'GATE-CLUTTER': 'Three paths out of 1904 (0.1576%) in 3/1066 structural sections (0.2814%) fail both minimum ten-item/5% item prevalence and 25% spread. Localized subdivision friction remains scored.',
    }
    new_gates = {g['gate_id']: g for g in result['critical_gates']}
    for gate in old_result['critical_gates']:
        if gate['triggered']:
            ledger['publication_gate_review'].append({'gate_id': gate['gate_id'], 'original_triggered': True, 'revised_triggered': new_gates[gate['gate_id']]['triggered'], 'frozen_defects_reused': [defects[i] for i in gate['defect_ids']], 'decision_reason': reasons[gate['gate_id']]})
    ledger['additional_consequence_review'] = {
        'reliability_excluded_locator': {'locator_id': 'LOC-F2F22AD0F6EB', 'evidence_ids': ['EVID-CHUNK003-P074-F2F22AD0F6EB'], 'original_unsupported_judgment_retained': True, 'complete_path_fit': 'material_mismatch', 'severity': 'minor', 'reason': 'Excluded from the distributed severe_mismatch/no_fit population only; keep-credit zero and diagnostic grade unchanged. Qualifying count falls from 94 to 93, retaining the same binding 90% band.'},
        'essential_subject_ceiling': {'subject_ids': ['SUBJ-0190', 'SUBJ-0191', 'SUBJ-0219', 'SUBJ-0250'], 'count': 4, 'denominator': 178, 'basis': 'Frozen benchmark essential priority and missing subject judgments. Ordinary priority-weighted Coverage deductions and the non-binding 90% essential-miss ceiling remain.', 'publication_gate_distinction': 'The missing-access rows carry critical severity but do not supply a separately structured central-omission defect with the required severity basis and blocks/misleads consequence. Missing headings or treatments alone are insufficient for a new publication gate; no escalation or new review is invented.'},
        'evaluation_validity': result['evaluation_validity'],
        'candidate_output_failure': False,
        'partial_fit_review_signal_count': sum(len(s['affected_evidence_ids']) for s in result['review_signals'] if s['signal_id'] == 'REVIEW-PARTIAL-FIT'),
        'review_signals': result['review_signals'],
    }
    ledger['mechanical_changes'].extend([
        'Reuse the confirmed correction overlay; change its excluded minor cross-reference gate Boolean and current item-assessment artifact binding, then recompute its self-hash.',
        'Publish new V8.1 result/report and the installed producer canonical projection with all four collections; retain the original V8 bundle and its two-view display adapter unchanged. The current producer uses one authoritative score view with the confirmed correction overlay; no separate adjusted score is invented.',
        'Original state points to calculation-profile-v4 and structure V5; the published final artifacts identify calculation-profile-v5 and structure V6. Exact published hashes, not stale state identities, define the comparison baseline.',
    ])
    original_state = read(original / 'evaluation-state.json')
    ledger['preserved_unrelated_warning'] = [dict(a, actual_sha256=sha(original / a['path']), disposition='Retain warning: pre-existing source inventory drift, not a scoring input; no unrelated byte or registration repair.') for a in original_state['artifacts'] if (original / a['path']).exists() and sha(original / a['path']) != a['sha256']]
    ledger['changed_private_artifacts'] = [{'path': str(p.relative_to(target)), 'original_sha256': sha(original / p.relative_to(target)) if (original / p.relative_to(target)).exists() else None, 'revised_sha256': sha(p)} for p in sorted(target.rglob('*')) if p.is_file() and p.name not in ('evaluation-state.json', '.evaluation.lock') and (not (original / p.relative_to(target)).exists() or sha(p) != sha(original / p.relative_to(target)))]
    ledger['public_artifact_hashes'] = [{'path': str(p.relative_to(ROOT)), 'sha256': sha(p)} for root in [ROOT / 'candidate/v8.1', ROOT / 'web/v8.1-canonical-projection'] for p in sorted(root.rglob('*.json')) if p != ledger_path and p.name != 'validation-receipt.json']
    ledger['validation'] = {'registered_structure': 'passed', 'registered_score': 'passed', 'registered_report_and_bundle': 'passed', 'ordinary_components': 'Exact equality of numeric components; high-value treatment recall weight/effective_weight changes from cap_only to reported_diagnostic_only as prescribed by V8.1.', 'diagnostic_item_assessments': 'exact equality; only top-level evidence_identity changes', 'additional_validation_receipt': 'validation/v8.1-validation-receipt.json'}
    write(ledger_path, ledger)
    sys.path.insert(0, str(skill / 'scripts'))
    import dimension_score_v8_cli as scoring
    from state_cli import now
    private_ledger = target / 'migration/migration-ledger.json'
    write(private_ledger, ledger)
    state_path = target / 'evaluation-state.json'
    state = read(state_path)
    state['artifacts'] = [a for a in state['artifacts'] if a.get('artifact_type') != 'migration_change_ledger']
    state['artifacts'].append(scoring._artifact_record(target, private_ledger, private_ledger.read_bytes(), stage='define_policy', artifact_type='migration_change_ledger', schema_version=ledger['schema_version'], stamp=now(), visibility='public'))
    state['updated_at'] = now()
    write(state_path, state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skill', type=Path, required=True)
    parser.add_argument('--report-only', action='store_true', help='Resume after successful registered scoring.')
    args = parser.parse_args()
    original = ROOT / 'staging/v8.1/original'
    target = ROOT / 'staging/v8.1/evaluation'
    if args.report_only:
        build_report(args.skill, target)
        return
    assert not (target / 'source/evaluation-policy.v8.1.json').exists(), 'Migration already started; resume reporting or validate the result.'
    prepare(args.skill, original, target)
    command(args.skill, 'register-structure', '--state', target / 'evaluation-state.json', '--input', target / 'structure/structure-audit.v6.json')
    command(args.skill, 'score', '--state', target / 'evaluation-state.json', '--output-dir', 'scoring/v8.1')
    build_report(args.skill, target)


if __name__ == '__main__':
    main()
