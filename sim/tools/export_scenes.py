"""Extract minimal scene metadata from an existing research tree, without changing it."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np


def export(source_root, output):
    source_root = Path(source_root).resolve()
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = source_root / 'runs/project-v3/automatic-road-v9/input-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    for item in manifest:
        conversion_path = source_root / 'samples' / item['sample'] / 'conversion.json'
        state_path = source_root / 'runs' / item['run'] / 'internal_0000.npz'
        conversion = json.loads(conversion_path.read_text(encoding='utf-8-sig'))
        with np.load(state_path, allow_pickle=False) as state:
            initial = state['center'].astype(float)
        raw_map = conversion['source_map'].replace('\\', '/')
        marker = 'data/nuplan/maps/'
        if marker not in raw_map:
            raise ValueError('Expected a nuPlan map beneath data/nuplan/maps')
        metadata = {
            'scene': item['scene'],
            'origin_xy_m': conversion['origin_xy_m'],
            'source_epsg': conversion['source_epsg'],
            'map_path': marker + raw_map.split(marker, 1)[1],
            'start_pose': {'xy': initial[:2].tolist(), 'heading': float(initial[6])},
            'provenance': {
                'manifest': str(manifest_path.relative_to(source_root)).replace('\\', '/'),
                'conversion': str(conversion_path.relative_to(source_root)).replace('\\', '/'),
                'state': str(state_path.relative_to(source_root)).replace('\\', '/'),
                'conversion_sha256': hashlib.sha256(conversion_path.read_bytes()).hexdigest(),
                'state_sha256': hashlib.sha256(state_path.read_bytes()).hexdigest(),
            },
        }
        (output / f"scene{item['scene']:02d}.json").write_text(
            json.dumps(metadata, indent=2) + '\n', encoding='utf-8')
    return len(manifest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'data/scenes')
    args = parser.parse_args()
    print(f'Exported {export(args.source_root, args.output)} scenes')
