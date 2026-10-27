"""Append completed windows without losing earlier work during partial resumes."""
import json
from pathlib import Path
from .paths import write_json


def read_manifest(path,expected_keys):
    expected=list(expected_keys)
    if len(set(expected))!=len(expected):raise ValueError('Experiment keys collide')
    path=Path(path);rows=json.loads(path.read_text()) if path.exists() else []
    if not isinstance(rows,list):raise ValueError('Manifest must be a list')
    keys=[r['key'] for r in rows]
    if len(set(keys))!=len(keys):raise ValueError('Duplicate completed window in manifest')
    if any(key not in expected for key in keys):raise ValueError('Manifest contains windows outside this experiment; use a new tag')
    return rows


def retain_completed_window(path,record,expected_keys):
    expected=list(expected_keys);previous=read_manifest(path,expected)
    if record['key'] not in expected:raise ValueError('Unexpected completed window')
    by_key={r['key']:r for r in previous}
    if record['key'] in by_key and by_key[record['key']]!=record:raise ValueError('Completed window changed; preserve old manifest and use a new tag')
    by_key[record['key']]=record
    merged=[by_key[key] for key in expected if key in by_key]
    if merged!=previous:write_json(path,merged)
    return merged
