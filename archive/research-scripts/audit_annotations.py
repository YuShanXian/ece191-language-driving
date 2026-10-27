"""Compare release/dashboard annotation schemas without assuming a frame rate."""
import csv
import json
from collections import Counter
from pathlib import Path

root = Path(__file__).resolve().parent.parent
report = {}
for filename, text_key, clip_key, duration_key in (
    ("release_annotationsV1.csv", "passenger_instruction", "clip_id", "window_duration_sec"),
    ("combined_annotations.csv", "label", "folder", "duration_sec"),
):
    path = root / "references" / filename
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        rows = list(reader)
    rates, invalid = Counter(), 0
    for row in rows:
        try:
            start, end, duration = float(row["start_frame"]), float(row["end_frame"]), float(row[duration_key])
            if duration <= 0 or end <= start:
                invalid += 1
            else:
                rates[round((end-start)/duration, 3)] += 1
        except (ValueError, TypeError, KeyError):
            invalid += 1
    report[filename] = {"rows": len(rows), "columns": fields,
        "nonblank_instructions": sum(bool(r[text_key].strip()) for r in rows),
        "unique_clips": len({r[clip_key] for r in rows}), "invalid_windows": invalid,
        "inferred_frame_rates": rates.most_common(10),
        "note": "Ratios are inferred from CSV windows, not verified video timestamps. Do not interchange the two exports."}
text = json.dumps(report, indent=2)
(root / "runs/setup-reports/annotation_audit.json").write_text(text, encoding="utf-8")
print(text)
