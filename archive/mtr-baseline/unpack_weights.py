"""Validate ZIP CRCs, record SHA256, and safely extract the approved weights."""
import hashlib
import json
from pathlib import Path
import zipfile

root = Path(__file__).resolve().parent.parent
archive = root / "archives/pretrained_weights.zip"
destination = root / "weights"
digest = hashlib.sha256()
with archive.open("rb") as stream:
    for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b""):
        digest.update(chunk)
with zipfile.ZipFile(archive) as z:
    members = z.infolist()
    for item in members:
        target = (destination / item.filename).resolve()
        if not target.is_relative_to(destination.resolve()):
            raise RuntimeError(f"Unsafe archive path: {item.filename}")
        if (item.external_attr >> 16) & 0o170000 == 0o120000:
            raise RuntimeError(f"Symlink in archive: {item.filename}")
    bad = z.testzip()
    if bad:
        raise RuntimeError(f"CRC failure: {bad}")
    z.extractall(destination)
result = {"sha256": digest.hexdigest(), "zip_crc": "passed",
          "files": [{"name": i.filename, "bytes": i.file_size} for i in members],
          "note": "Local integrity record; upstream did not supply a comparison hash."}
(root / "runs/setup-reports/weights-manifest.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
print(json.dumps(result, indent=2))
