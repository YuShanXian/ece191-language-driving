"""Inventory the official archive and extract only its validation/test ZIP."""
import json
from pathlib import Path
import shutil
import zipfile

root = Path(__file__).resolve().parent.parent
with zipfile.ZipFile(root / "archives/data.zip") as archive:
    inventory = [{"name": x.filename, "bytes": x.file_size, "compressed": x.compress_size}
                 for x in archive.infolist()]
    (root / "runs/setup-reports/data-archive-inventory.json").write_text(json.dumps(inventory, indent=2))
    print(json.dumps(inventory, indent=2), flush=True)
    matches = [x for x in archive.infolist() if x.filename.endswith("/for_val_and_test.zip")]
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one validation/test archive; inspect inventory")
    dest = root / "archives/for_val_and_test.zip"
    if dest.exists():
        raise FileExistsError(dest)
    with archive.open(matches[0]) as src, dest.open("wb") as out:
        shutil.copyfileobj(src, out, length=8*1024*1024)
with zipfile.ZipFile(dest) as archive:
    inventory = [{"name": x.filename, "bytes": x.file_size} for x in archive.infolist()]
    (root / "runs/setup-reports/validation-archive-inventory.json").write_text(json.dumps(inventory, indent=2))
    print("Nested archive sample:", json.dumps(inventory[:12], indent=2), flush=True)
