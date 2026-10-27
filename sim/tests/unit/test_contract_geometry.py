"""Fast contract, scene-export, and synthetic geometry tests; no map or browser."""
import importlib.util
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import numpy as np

SIM = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SIM))
from engine.contract import validate, validate_stage
from engine.normalize import normalize
from engine.geometry import validate_path, reverse_clearance
from engine.planner import stage
from shapely.geometry import box


class ContractGeometryTests(unittest.TestCase):
    def test_provider_adapters_use_engine_contract(self):
        sys.path.insert(0, str(SIM / 'parser'))
        import parser_backends as parser
        value = {'status': 'parsed', 'stages': [stage('go_straight')], 'unresolved_text': [], 'explanation': ''}
        def reply(command, **kwargs):
            if '-o' in command:
                Path(command[command.index('-o') + 1]).write_text(json.dumps(value))
            return SimpleNamespace(returncode=0, stdout=json.dumps({'structured_output': value}), stderr='')
        with tempfile.TemporaryDirectory(dir=SIM / 'tests/results') as folder:
            with patch.dict('os.environ', {'DEMO_TRACE_ROOT': folder}), patch.object(parser, 'executable', side_effect=lambda provider: provider), patch.object(parser.subprocess, 'run', side_effect=reply):
                for provider in ['codex', 'claude', 'gemini', 'antigravity']:
                    model = next(m for m in parser.MODELS if m['provider'] == provider)
                    with self.subTest(provider=provider):
                        result = parser.parse('Go straight', model['id'])
                        self.assertEqual(result['parsed']['stages'][0]['action'], 'go_straight')
                        validate(result['parsed'])

    def test_native_route_priority(self):
        import runpy
        runpy.run_path(str(Path(__file__).with_name('route-priority.py')))

    def test_schema_rejects_unknown_and_nonfinite_values(self):
        value = stage('go_straight')
        validate_stage(value)
        for change in [{'action': 'fly'}, {'travel_distance_m': math.nan}, {'extra': 1}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_stage({**value, **change})

    def test_lane_expansion_preserves_order_and_trigger(self):
        plan = normalize({'stages': [{**stage('lane_change_left'), 'lane_number': 3}, stage('turn_right')]})
        self.assertEqual([x['action'] for x in plan['stages']], ['lane_change_left'] * 3 + ['turn_right'])
        self.assertEqual([x['trigger'] for x in plan['stages'][:3]], ['now', 'after_previous', 'after_previous'])

    def test_distance_stop_preserves_target(self):
        plan = normalize({'stages': [{**stage('go_straight'), 'travel_distance_m': 30}, {**stage('stop'), 'trigger': 'after_previous'}]})
        self.assertTrue(plan['stages'][0]['stop_at_end'])
        self.assertEqual(plan['stages'][0]['travel_distance_m'], 30)

    def test_unsupported_condition_is_not_erased(self):
        value = {**stage('turn_right'), 'constraints': ['Only when the signal is green']}
        self.assertEqual(normalize({'stages': [value]})['stages'][0]['constraints'], value['constraints'])

    def test_geometry_rejects_corner_and_reversal(self):
        self.assertTrue(validate_path([[0, 0], [10, 0], [20, 0]])[0])
        self.assertFalse(validate_path([[0, 0], [10, 0], [10, 10]])[0])
        self.assertFalse(validate_path([[0, 0], [10, 0], [0, 0]])[0])

    def test_reverse_checks_vehicle_body(self):
        route = {'points': [[0, 0], [-10, 0]]}
        self.assertTrue(reverse_clearance(route, box(-20, -2, 10, 2)))
        self.assertFalse(reverse_clearance(route, box(-20, -.5, 10, .5)))

    def test_scene_metadata_is_portable_and_complete(self):
        files = sorted((SIM / 'data/scenes').glob('scene*.json'))
        self.assertEqual(len(files), 7)
        for file in files:
            data = json.loads(file.read_text())
            self.assertEqual(len(data['origin_xy_m']), 2)
            self.assertEqual(len(data['start_pose']['xy']), 2)
            self.assertTrue(math.isfinite(data['start_pose']['heading']))
            self.assertTrue(data['map_path'].startswith('data/nuplan/maps/'))
            self.assertNotIn(':', data['map_path'])

    def test_export_reproduces_pose_and_relative_map(self):
        spec = importlib.util.spec_from_file_location('export_scenes', SIM / 'tools/export_scenes.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(dir=SIM / 'tests/results') as folder:
            root = Path(folder)
            for sub in ['runs/project-v3/automatic-road-v9', 'samples/example', 'runs/example']:
                (root / sub).mkdir(parents=True)
            (root / 'runs/project-v3/automatic-road-v9/input-manifest.json').write_text(json.dumps([{'scene': 1, 'sample': 'example', 'run': 'example'}]))
            (root / 'samples/example/conversion.json').write_text(json.dumps({'origin_xy_m': [1, 2], 'source_epsg': 32611, 'source_map': '/external/data/nuplan/maps/example/map.gpkg'}))
            np.savez(root / 'runs/example/internal_0000.npz', center=np.array([3, 4, 0, 0, 0, 0, .5]))
            self.assertEqual(module.export(root, root / 'output'), 1)
            data = json.loads((root / 'output/scene01.json').read_text())
            self.assertEqual(data['start_pose'], {'xy': [3., 4.], 'heading': .5})
            self.assertEqual(data['map_path'], 'data/nuplan/maps/example/map.gpkg')


if __name__ == '__main__':
    (SIM / 'tests/results').mkdir(exist_ok=True)
    unittest.main(verbosity=2)
