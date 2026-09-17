#!/usr/bin/env python3
"""Migrate frozen V8.1 evidence to V8.2; keep all private baselines intact."""
import argparse
import copy
import os
import shutil
import subprocess
import sys
from pathlib import Path
from migrate_v8_1 import ROOT, read, sha, write, command

RELEASE = 'c11c6ccb16000fe79646af16b7be01f6cbeeac78'
BASE = ROOT / 'staging/v8.1/evaluation'
TARGET = ROOT / 'staging/v8.2/evaluation'
PUBLIC = ROOT / 'candidate/v8.2'


def reviewed_uncertainty_scopes(structure):
    # Explicit mapping after reviewing all 26 frozen summaries and affected IDs.
    # Unknown future records require review rather than a legacy-kind heuristic.
    locators = {
        'AC2896EED86C', '74D3E6FF1760', 'C0CFFDC75062', '85E43F84BFB1',
        '003F71762571', '07D39DBEB6CD', 'B69459B168C4', '1D03ABE81781',
        '9217D7991F28', '8935B2B37159', '923ACF3DDFBB', '21C27B76EE6C',
        'B6E7290BF6C4',
    }
    subjects = {'0175', '0179', '0182', '0372', '0376', '0379', '0385',
                '0395', '0403', '0557', '0568', '0587', '0591'}
    expected = {'UNCERTAINTY-LOC-' + item for item in locators} | {'UNCERTAINTY-SUBJ-' + item for item in subjects}
    assert {r['uncertainty_id'] for r in structure['uncertainties']} == expected
    scopes = []
    for record in structure['uncertainties']:
        identity = record['uncertainty_id']
        atomic = identity in {'UNCERTAINTY-LOC-' + item for item in locators}
        target = identity.removeprefix('UNCERTAINTY-')
        assert target in record['affected_item_ids'] and record['evidence_ids']
        scopes.append({
            'uncertainty_id': identity,
            'scope': 'locator_support' if atomic else 'benchmark_access',
            'target_ids': [target], 'evidence_ids': record['evidence_ids'],
            'rationale': (
                'The preserved finding addresses complete-heading support at this named locator destination. Its heading path is contextual; the finding does not assert uncertainty about every sibling locator.'
                if atomic else
                'The preserved finding addresses whether the delivered routes satisfy this benchmark subject or reader task. It does not assert uncertainty about the correctness of every locator on those routes.'
            ),
        })
    return scopes


def prepare(skill):
    import dimension_score_v8_cli as scoring
    import scoring_core as core
    from state_cli import now
    assert not TARGET.exists(), 'Migration exists: resume with --report-only or validate.'
    shutil.copytree(BASE, TARGET)
    stamp = now()
    state = read(BASE / 'evaluation-state.json')
    old_path = BASE / 'source/evaluation-policy.v4.json'
    base_path = BASE / 'source/evaluation-policy.v8.1.json'
    old, base = read(old_path), read(base_path)
    inp_path = TARGET / 'migration/policy-build-input.v8.2.json'
    def ref(path):
        return {'path': os.path.relpath(path, inp_path.parent), 'sha256': sha(path)}
    stages = ['page_mapping', 'chunk_definition', 'source_subject_discovery', 'benchmark_synthesis', 'benchmark_review', 'benchmark_freeze', 'candidate_normalization', 'locator_audit', 'missing_access_audit']
    reused = {stage: {'rerun': False, 'evidence': [ref(BASE / a['path']) for a in state['artifacts'] if a['stage'] == stage]} for stage in stages}
    source = {k: copy.deepcopy(base[k]) for k in ('source_scope', 'audience', 'audit_design', 'deviations')}
    source.update(schema_version='subject-index-policy-build-input-v1', policy_id=old['policy_id'] + '-retrospective-v8.2')
    source['retrospective_migration'] = {
        'original_policy': {'policy_id': old['policy_id'], 'policy_profile_id': old['policy_profile']['id'], 'policy_sha256': old['policy_sha256'], 'artifact': ref(old_path), 'freeze': old['freeze']},
        'migrated_at': stamp, 'candidate_seen': True,
        'authorization': {'authorized_by': 'User', 'reference': 'codex://threads/01a0aaf9-30c3-7462-b507-9d7851e230c2; explicit request to proceed and coordinate the combined migration'},
        'change_ledger_reference': 'candidate/v8.2/migration-ledger.json', 'reused_stages': reused,
    }
    write(inp_path, source)
    policy_path = TARGET / 'source/evaluation-policy.v8.2.json'
    subprocess.run([sys.executable, str(skill / 'scripts/policy_cli.py'), 'build', '--input', str(inp_path), '--original-policy', str(old_path), '--base-policy', str(base_path), '--output', str(policy_path)], check=True)
    policy = read(policy_path)
    # V8.1 used a project-specific legacy name; native provenance supersedes it.
    policy['policy_profile'].pop('migration', None)
    for area in policy['content_policies'].values():
        area['profile'] = policy['policy_profile']['id']
    policy['policy_sha256'] = core.canonical_hash(policy, 'policy_sha256')
    scoring.validate_v8_policy(policy)
    write(policy_path, policy)
    structure = read(BASE / 'structure/structure-audit.v6.json')
    inventory = read(next(BASE.glob('candidates/*/item-inventory.draft.v2.json')))
    references = {r['reference_id']: r for r in inventory['cross_references']}
    for row in structure['cross_reference_judgments']:
        delivered = references[row['reference_id']]
        broken = row['reference_id'] == 'XREF-6E6F54660707'
        assert broken or row['reference_id'] == 'XREF-9A63B6DC42BB'
        row['target_resolution'] = {
            'status': 'no_valid_destination' if broken else 'defective_but_identifiable_destination',
            'reference_type': delivered['reference_type'], 'target_display': delivered['target_display'],
            'resolved_path_ids': [] if broken else ['PATH-26704D6AB01B'],
            'evidence_ids': ['EVID-FROZEN-' + row['reference_id']], 'rationale': row['summary'],
        }
    structure['uncertainty_gate_scopes'] = reviewed_uncertainty_scopes(structure)
    structure_path = TARGET / 'structure/structure-audit.v8.2.v6.json'
    write(structure_path, structure)
    reopened = ('define_policy', 'structure_audit', 'scoring', 'web_report')
    removed = [a for a in state['artifacts'] if a['stage'] in reopened]
    state['artifacts'] = [a for a in state['artifacts'] if a['stage'] not in reopened]
    state['configuration'].update(policy_profile=policy['policy_profile']['id'], rubric_version=scoring.RUBRIC_VERSION, scoring_identity={'rubric_version': scoring.RUBRIC_VERSION, 'dimension_calculation_profile': scoring.CALCULATION_PROFILE})
    state['artifacts'].append(scoring._artifact_record(TARGET, policy_path, policy_path.read_bytes(), stage='define_policy', artifact_type='evaluation-policy-v4', schema_version=policy['schema_version'], stamp=stamp))
    for stage in ('structure_audit', 'scoring', 'web_report'):
        state['stages'][stage] = {'status': 'not_started', 'updated_at': stamp, 'notes': ['Authorized targeted V8.2 migration; frozen V8.1 state and all evidence remain in the sibling baseline.']}
    state['stages']['define_policy']['notes'].append('Native retrospective V8.2 policy records actual candidate visibility and original candidate-blind freeze separately. No new review or approval claimed.')
    state['updated_at'] = stamp
    write(TARGET / 'evaluation-state.json', state)
    ledger = {
        'schema_version': 'ohfr-targeted-v8.2-migration-ledger-v1', 'methodology_commit': RELEASE,
        'installation_receipt_sha256': sha(skill / 'installation-receipt.json'), 'intermediate_checkpoint': {'methodology_commit': 'adeb69171a3278893e8b7ebb3c664ee5bd428efe', 'public_commit': '994be0d', 'private_archive_sha256': '68406fe12f19eabacaf95cb04211ec597659f101bb5bff01225cdd4df78d6d4e'}, 'migrated_at': stamp,
        'baseline': {'public_commit': '5b56924', 'score': '89.38', 'canonical_state_sha256': sha(BASE / 'evaluation-state.json'), 'recovery_disclosure': 'validation/v8.1-private-recovery.json'},
        'policy_build_input_sha256': sha(inp_path), 'policy_file_sha256': sha(policy_path), 'policy_sha256': policy['policy_sha256'],
        'original_policy_freeze': old['freeze'], 'migration_freeze': policy['freeze'],
        'reused_without_rerun': stages,
        'changes': ['Apply released V8.2 direct wrong-destination gates and native retrospective migration provenance.', 'Remove obsolete project-specific policy_profile.migration metadata; preserve it in the exact V8.1 archive.', 'Update content-policy profile labels only; scope, audience, audit design, density, scoring weights and judgments are preserved.', 'Encode the two existing reference exceptions as confirmed no destination and defective but identifiable destination, using exact delivered reference labels and frozen audit evidence.', 'Add explicit gate-applicability scopes to 13 atomic locator uncertainties and 13 benchmark-access uncertainties; preserve every original uncertainty record unchanged.', 'Re-register structure, score and report using the installed producer; update correction-overlay artifact bindings and remaining broken-reference gate consequence.'],
        'resolution_evidence_mapping': [{'evidence_id': 'EVID-FROZEN-' + r['reference_id'], 'source_artifact_sha256': sha(BASE / 'structure/structure-audit.v6.json'), 'reference_id': r['reference_id'], 'original_evidence_ids': r['evidence_ids'], 'basis': 'Stable identifier assigned to an existing frozen finding; no new judgment.'} for r in structure['cross_reference_judgments']],
        'uncertainty_scope_supplement': structure['uncertainty_gate_scopes'],
        'structure_target_resolutions': [{'reference_id': r['reference_id'], **r['target_resolution']} for r in structure['cross_reference_judgments']],
        'baseline_archive_inventory': [{'path': str(p.relative_to(BASE)), 'sha256': sha(p)} for p in sorted(BASE.rglob('*')) if p.is_file()],
        'prior_state_records_preserved_in_baseline': [{'path': a['path'], 'sha256': a['sha256']} for a in removed],
    }
    write(PUBLIC / 'migration-ledger.json', ledger)
    command(skill, 'register-structure', '--state', TARGET / 'evaluation-state.json', '--input', structure_path)
    command(skill, 'score', '--state', TARGET / 'evaluation-state.json', '--output-dir', 'scoring/v8.2')


def report(skill):
    import dimension_score_v8_cli as scoring
    import scoring_core as core
    from state_cli import now
    state_path = TARGET / 'evaluation-state.json'
    state = read(state_path)
    assert not (TARGET / 'scoring/v8.2/web-report.v10.json').exists()
    overlay = read(BASE / 'corrections/correction-overlay.v1.json')
    overlay['cross_reference_resolution']['cross_reference_gate_triggered_after_correction'] = True
    for schema, key in [('subject-index-item-assessments-v7', 'v8_item_assessment_artifact'), ('structure-audit-v6', 'v8_structure_artifact')]:
        a = next(a for a in state['artifacts'] if a.get('schema_version') == schema)
        overlay['provenance'][key].update(artifact_path=a['path'], sha256=a['sha256'])
    overlay['provenance']['version_bridge'] += ' V8.2 retains the confirmed correction facts; the remaining individual-regiments reference has no valid destination and now directly blocks publication. Current item and structure bindings are updated.'
    overlay['overlay_sha256'] = core.canonical_hash(overlay, 'overlay_sha256')
    op = TARGET / 'corrections/correction-overlay.v8.2.v1.json'
    write(op, overlay)
    state['artifacts'].append(scoring._artifact_record(TARGET, op, op.read_bytes(), stage='structure_audit', artifact_type='correction_overlay', schema_version=overlay['schema_version'], stamp=now(), visibility='public'))
    write(state_path, state)
    command(skill, 'build-report', '--state', state_path, '--output', 'scoring/v8.2/web-report.v10.json', '--bundle-output', 'scoring/v8.2/v8-canonical-projection')
    for name in ('evaluation-result.v12.json', 'web-report.v10.json'):
        shutil.copyfile(TARGET / 'scoring/v8.2' / name, PUBLIC / name)
    shutil.copytree(TARGET / 'scoring/v8.2/v8-canonical-projection', ROOT / 'web/v8.2-canonical-projection')


def finish():
    import dimension_score_v8_cli as scoring
    from state_cli import now
    old = read(BASE / 'scoring/v8.1/dimension-calculations.v6.json')
    new = read(TARGET / 'scoring/v8.2/dimension-calculations.v6.json')
    result = read(PUBLIC / 'evaluation-result.v12.json')
    projection = read(ROOT / 'web/v8.2-canonical-projection/projection.v1.json')
    ledger = read(PUBLIC / 'migration-ledger.json')
    ledger['score_comparison'] = {'original': old['overall_percentage'], 'revised': new['overall_percentage']}
    ledger['dimension_comparison'] = []
    for before, after in zip(old['dimensions'], new['dimensions'], strict=True):
        # Only formula identity labels and artifact bindings change in V8.2.
        assert {k: v for k, v in before.items() if k not in ('formula_id', 'input_artifacts')} == {k: v for k, v in after.items() if k not in ('formula_id', 'input_artifacts')}, after['dimension_id']
        ledger['dimension_comparison'].append({'dimension_id': after['dimension_id'], 'all_components_and_caps_unchanged': True, 'pre_cap_percentage': after['pre_cap_percentage'], 'post_cap_percentage': after['post_cap_percentage'], 'weighted_contribution': after['weighted_contribution']})
    assert old['overall_percentage'] == new['overall_percentage']
    ledger['triggered_gates'] = [g for g in result['critical_gates'] if g['triggered']]
    ledger['gate_assessment'] = result['gate_assessment']
    ledger['evaluation_validity'] = result['evaluation_validity']
    ledger['readiness'] = projection['score_views']['views'][0]['readiness']
    ledger['public_artifact_hashes'] = [{'path': str(p.relative_to(ROOT)), 'sha256': sha(p)} for folder in (PUBLIC, ROOT / 'web/v8.2-canonical-projection') for p in sorted(folder.rglob('*.json')) if p.name != 'migration-ledger.json']
    ledger['changed_private_artifacts'] = [{'path': str(p.relative_to(TARGET)), 'sha256': sha(p)} for p in sorted(TARGET.rglob('*')) if p.is_file() and p.name not in ('evaluation-state.json', '.evaluation.lock') and (not (BASE / p.relative_to(TARGET)).exists() or sha(p) != sha(BASE / p.relative_to(TARGET)))]
    write(PUBLIC / 'migration-ledger.json', ledger)
    private = TARGET / 'migration/migration-ledger.v8.2.json'
    write(private, ledger)
    state_path = TARGET / 'evaluation-state.json'
    state = read(state_path)
    state['artifacts'].append(scoring._artifact_record(TARGET, private, private.read_bytes(), stage='define_policy', artifact_type='migration_change_ledger', schema_version=ledger['schema_version'], stamp=now(), visibility='public'))
    state['updated_at'] = now()
    write(state_path, state)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skill', type=Path, required=True)
    parser.add_argument('--report-only', action='store_true')
    args = parser.parse_args()
    sys.path.insert(0, str(args.skill / 'scripts'))
    if not args.report_only:
        prepare(args.skill)
    report(args.skill)
    finish()


if __name__ == '__main__':
    main()
