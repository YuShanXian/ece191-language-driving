"""Extract one unchanged official validation scenario and its matching metadata."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import pickle
import zipfile
import numpy as np

root = Path(__file__).resolve().parent.parent
dest = root / "samples/val"
dest.mkdir(parents=True, exist_ok=False)
with zipfile.ZipFile(root / "archives/for_val_and_test.zip") as archive:
    candidates = [i for i in archive.infolist() if i.filename.startswith("val/")
                  and PurePosixPath(i.filename).name.startswith("sd_") and i.filename.endswith(".pkl")]
    item = min(candidates, key=lambda i: i.file_size)
    name = PurePosixPath(item.filename).name
    shard = str(PurePosixPath(item.filename).parent)
    raw = archive.read(item)
    (dest / name).write_bytes(raw)
    summary = pickle.loads(archive.read(shard + "/dataset_summary.pkl"))
    assert name in summary, list(summary)[:3]
    with (dest / "dataset_summary.pkl").open("wb") as f:
        pickle.dump({name: summary[name]}, f)
    with (dest / "dataset_mapping.pkl").open("wb") as f:
        pickle.dump({name: ""}, f)
    scenario = pickle.loads(raw)
    ts = np.asarray(scenario['metadata']['ts'])
    result = {"source_file_id": "1Fv3EPN_ychJYuHU8pwhqTgKxrTfpbARO",
        "archive_member": item.filename, "scenario_sha256": hashlib.sha256(raw).hexdigest(),
        "scenario_bytes": len(raw), "zip_member_crc": "passed", "tracks": len(scenario['tracks']),
        "map_features": len(scenario['map_features']), "timesteps": len(ts),
        "timestamp_first": float(ts[0]), "timestamp_median_step": float(np.median(np.diff(ts))),
        "metadata_keys": list(scenario['metadata']), "scenario_keys": list(scenario),
        "track_state_keys": list(next(iter(scenario['tracks'].values()))['state'])}
(root / "runs/setup-reports/sample-provenance.json").write_text(json.dumps(result, indent=2))
print(json.dumps(result, indent=2))
