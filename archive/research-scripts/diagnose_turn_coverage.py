"""Explain frozen turn coverage without changing any model, filter or planner."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import pickle
import numpy as np
from mtr_project.paths import ROOT, sha256, write_json
from mtr_project.turn_attribution import BUCKETS, attribute_candidates, curve_heading_change, curve_bucket


def plot_report(report, destination):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors = ['#9aa8b7', '#dce4ec', '#d2a568', '#ce7460', '#198687']
    labels = ['Route unresolved', 'No requested turn on matched route',
              'Turn + incompatible other actions', 'Matching turn, rejected', 'Matching turn, passed']
    fig, axes = plt.subplots(1, 2, figsize=(14, 7), sharey=True)
    windows = report['windows']
    y = np.arange(len(windows))
    for ax, action in zip(axes, ['turn_left', 'turn_right']):
        offset = np.zeros(len(windows), dtype=int)
        for key, color, label in zip(BUCKETS, colors, labels):
            values = np.array([r['actions'][action]['counts'][key] for r in windows])
            ax.barh(y, values, left=offset, color=color, label=label)
            offset += values
        ax.set_xlim(0, 64)
        ax.set_xlabel('Candidates / 64 (each candidate counted once)')
        ax.set_title(action.replace('_', ' ').title())
        ax.spines[['top', 'right']].set_visible(False)
    axes[0].set_yticks(y, [r['key'] for r in windows])
    axes[0].invert_yaxis()
    fig.suptitle('Where turn candidates are lost: 13 fixed windows', fontsize=17, weight='bold')
    fig.legend(*axes[0].get_legend_handles_labels(), loc='lower center', ncol=2,
               bbox_to_anchor=(.5, .04), frameon=False)
    fig.text(.02, .015, 'Frozen derived candidates and existing checks. Unresolved routes cannot be assigned a reliable turn label. No driving-success claim.', fontsize=9)
    fig.tight_layout(rect=[0, .18, 1, .94])
    fig.savefig(destination/'turn-attribution.png', dpi=170)
    fig.savefig(destination/'turn-attribution.pdf')
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', help='New project-relative output folder; never overwrite')
    args = parser.parse_args()
    path = ROOT/'runs/project-v2/turn-challenge-v1/evaluation.json'
    report = json.loads(path.read_text())
    sources = {str(path.relative_to(ROOT)): sha256(path)}
    windows = []
    for result in report['windows']:
        item = result['window']
        folder = ROOT/'runs'/item['run']
        sample = ROOT/'samples'/item['sample']
        conversion_path = sample/'conversion.json'
        conversion = json.loads(conversion_path.read_text())
        scenario_path = sample/conversion['scenario']
        screen_path = folder/'anchored_feasibility.json'
        raw_path = folder/'internal_0000.npz'
        refined_path = folder/'refined_v2_candidates.npz'
        for source in [conversion_path, scenario_path, screen_path, raw_path, refined_path]:
            name = str(source.relative_to(ROOT))
            digest = sha256(source)
            if report['source_sha256'].get(name) != digest:
                raise ValueError('Frozen input changed: '+name)
            sources[name] = digest
        rows = json.loads(screen_path.read_text())['candidates']
        with np.load(raw_path) as cached:
            raw = cached['world_xy'].copy()
            center = cached['center'].copy()
            final5 = [int(x)+1 for x in cached['selected_indices']]
        with np.load(refined_path) as cached:
            refined = cached['world_xy'].copy()
        if raw.shape != (64, 60, 2) or refined.shape != raw.shape or len(rows) != 64:
            raise ValueError('Unexpected candidate dimensions')
        if [r['candidate'] for r in rows] != list(range(1,65)) or final5 != result['original_final5']:
            raise ValueError('Candidate identity mismatch')
        with scenario_path.open('rb') as stream:
            ego = pickle.load(stream)['tracks']['ego']['state']
        future = ego['position'][20:81, :2]
        if not np.all(ego['valid'][20:81]) or not np.isfinite(future).all():
            raise ValueError('Incomplete recorded future')
        if not np.allclose(center[:2], future[0], atol=1e-4):
            raise ValueError('Anchor coordinate mismatch')
        times = np.asarray(conversion['timestamp_us'])
        if times[20] != item['timestamp_us'] or len(times) != 81 or np.max(np.abs(np.diff(times)/1e6-.1)) >= .002:
            raise ValueError('Unexpected time grid')
        actions = {action: attribute_candidates(rows, action, result['speed_mps'])
                   for action in ['turn_left', 'turn_right']}
        for choice in result['choices']:
            attribution = actions[choice['action']]
            if attribution['candidate_ids']['matching_and_passed'] != choice['all64']['matching_candidates']:
                raise ValueError('Attribution does not reproduce frozen selection')
            matched = sorted(attribution['candidate_ids']['matching_but_rejected'] + attribution['candidate_ids']['matching_and_passed'])
            if matched != choice['matching_action_before_other_checks']:
                raise ValueError('Action attribution mismatch')
        shape = {}
        errors = {}
        for name, trajectories in [('raw', raw), ('derived', refined)]:
            changes = [curve_heading_change(np.vstack([center[:2], xy]), float(center[6])) for xy in trajectories]
            shape[name] = {'endpoint_heading_change_deg': changes,
                           'counts': dict(Counter(curve_bucket(x) for x in changes))}
            distance = np.linalg.norm(trajectories - future[None, 1:], axis=-1)
            ade = distance.mean(axis=1)
            fde = distance[:, -1]
            errors[name] = {'oracle_min_ADE_m': float(ade.min()), 'oracle_min_ADE_candidate': int(ade.argmin()+1),
                            'oracle_min_FDE_m': float(fde.min()), 'oracle_min_FDE_candidate': int(fde.argmin()+1)}
        recorded_delta = float(np.degrees(np.unwrap(ego['heading'][20:81].astype(float))[-1]-float(ego['heading'][20])))
        windows.append({'key': item['key'], 'sampling': item['sampling'], 'speed_mps': result['speed_mps'],
                        'actions': actions, 'shape_only_proxy': shape, 'offline_oracle_errors': errors,
                        'recorded_future_heading_change_deg': recorded_delta,
                        'recorded_heading_proxy': curve_bucket(recorded_delta),
                        'route_failure_counts': dict(Counter(r['route'].get('failure', 'unspecified') for r in rows if not r['route'].get('matched')))})
    summary = {'windows': len(windows), 'candidates': 64*len(windows), 'actions': {}}
    for action in ['turn_left', 'turn_right']:
        counts = Counter()
        rejections = Counter()
        combinations = Counter()
        for row in windows:
            counts.update(row['actions'][action]['counts'])
            rejections.update(row['actions'][action]['matching_rejections_overlapping'])
            combinations.update(row['actions'][action]['matching_rejection_combinations_exclusive'])
        summary['actions'][action] = {'counts': dict(counts), 'matching_rejections_overlapping': dict(rejections),
                                     'matching_rejection_combinations_exclusive': dict(combinations),
                                     'windows_with_action_before_other_checks': sum(bool(r['actions'][action]['counts']['matching_but_rejected'] + r['actions'][action]['counts']['matching_and_passed']) for r in windows),
                                     'windows_with_passing_action': sum(bool(r['actions'][action]['counts']['matching_and_passed']) for r in windows)}
    summary['recorded_heading_proxy_windows'] = dict(Counter(r['recorded_heading_proxy'] for r in windows))
    summary['shape_only_proxy_candidates'] = {name: dict(sum((Counter(r['shape_only_proxy'][name]['counts']) for r in windows), Counter())) for name in ['raw', 'derived']}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    destination = (ROOT/(args.output or ('runs/project-v3/turn-attribution/'+stamp))).resolve()
    if not destination.is_relative_to((ROOT/'runs').resolve()):
        raise ValueError('Output must stay under project runs')
    destination.mkdir(parents=True, exist_ok=False)
    output = {'created_utc': stamp, 'summary': summary, 'windows': windows, 'source_sha256': sources,
              'implementation_sha256': {name: sha256(ROOT/name) for name in ['scripts/diagnose_turn_coverage.py', 'scripts/mtr_project/turn_attribution.py', 'scripts/language_selector.py', 'scripts/trajectory_checks.py']},
              'scope': ['Offline descriptive diagnosis, not an online selection change.',
                        'Raw endpoint heading is a shape proxy, not a road-matched legal or completed turn.',
                        'Action attribution uses frozen DERIVED paths and shared baseline route labels.',
                        'Rejection reasons overlap; exclusive combinations and buckets are separately reported.',
                        'Recorded future and oracle errors are evaluation-only; oracle IDs must never be used for selection.',
                        'Recorded heading proxies do not establish which alternative turns were legally available.',
                        '13 windows are a fixed development diagnostic set, not a representative driving benchmark.']}
    write_json(destination/'diagnosis.json', output)
    plot_report(output, destination)
    write_json(destination/'artifacts.json', {name: sha256(destination/name) for name in ['diagnosis.json', 'turn-attribution.png', 'turn-attribution.pdf']})
    print(json.dumps({'output': str(destination), 'summary': summary}, indent=2))


if __name__ == '__main__':
    main()
