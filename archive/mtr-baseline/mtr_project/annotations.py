"""Versioned doPlan records and explicit, evidence-labelled frame alignment.

Annotation windows are NOT instruction utterance or maneuver onset labels.
The GPS row mapping remains conditional until video frame parity is verified.
"""
import csv
import math
from statistics import median
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from .paths import sha256

@dataclass(frozen=True)
class Annotation:
    annotation_id: str
    clip_id: str
    start_frame: int
    end_frame: int
    duration_seconds: float
    instruction: str
    referential_label: str
    annotator_id: str

    @property
    def recording_id(self):
        # Segments from a single driving recording must never cross data splits.
        return self.clip_id.rsplit('_', 2)[0]

def load_release(path):
    records, rejected = [], []
    seen = set()
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        for line, row in enumerate(csv.DictReader(stream), 2):
            try:
                item = Annotation(row['annotation_id'], row['clip_id'],
                                  int(row['start_frame']), int(row['end_frame']),
                                  float(row['window_duration_sec']),
                                  row['passenger_instruction'].strip(),
                                  row['referential_label'], row['annotator_id'])
                if item.annotation_id in seen:
                    raise ValueError('duplicate_annotation_id')
                if item.start_frame < 0 or item.end_frame <= item.start_frame:
                    raise ValueError('invalid_frame_interval')
                if not math.isfinite(item.duration_seconds) or item.duration_seconds <= 0:
                    raise ValueError('invalid_duration')
                if '/' in item.clip_id or '\\' in item.clip_id or '..' in item.clip_id:
                    raise ValueError('invalid_clip_id')
                seen.add(item.annotation_id)
                records.append(item)
            except (KeyError, ValueError) as error:
                rejected.append({'line': line, 'reason': str(error)})
    return records, {'file': str(path), 'sha256': sha256(path),
                     'valid_records': len(records), 'rejected_records': rejected}

def align_to_gps(annotation, gps_path, database_timestamps, video_frames_verified=False):
    with Path(gps_path).open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    ids = [int(row['frame']) for row in rows]
    times = [int(row['timestamp_us']) for row in rows]
    if not times or any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError('GPS timestamps must be strictly increasing')
    if len(ids) != len(set(ids)) or ids != sorted(ids):
        raise ValueError('GPS rows need explicit frame ordering/deduplication')
    available = set(int(t) for t in database_timestamps)
    exact = sum(t in available for t in times)
    # userLabeler starts at frame 0 and uses the video frame index. The CSV frame
    # column records source-iteration numbers; it must NOT be treated as row index.
    candidates = []
    for offset in (0, -1):
        start, end = annotation.start_frame + offset, annotation.end_frame + offset
        if not 0 <= start < end <= len(times):
            candidates.append({'video_index_offset': offset, 'status': 'out_of_range'})
            continue
        # The labeler saves [start, end): seeks start, then stops when the
        # next-read position reaches end. end == number_of_frames is valid.
        end_boundary = times[end] if end < len(times) else times[-1] + round(median(b-a for a,b in zip(times,times[1:])))
        duration = (end_boundary - times[start]) / 1e6
        candidates.append({'video_index_offset': offset, 'status': 'mapped',
                           'start_timestamp_us': times[start], 'end_timestamp_us': end_boundary,
                           'last_displayed_timestamp_us': times[end-1], 'end_frame_exclusive': end,
                           'end_boundary_inferred': end == len(times),
                           'duration_sec': duration, 'duration_error_sec': duration-annotation.duration_seconds,
                           'start_gps_source_frame': ids[start], 'last_displayed_gps_source_frame': ids[end-1],
                           'endpoints_in_database': times[start] in available and times[end-1] in available})
    mapped = next((x for x in candidates if x['video_index_offset'] == 0 and x['status'] == 'mapped'), None)
    valid = bool(mapped and mapped['endpoints_in_database'] and exact == len(times)
                 and abs(mapped['duration_error_sec']) <= .25)
    return {'annotation': asdict(annotation), 'gps_sha256': sha256(gps_path),
            'gps_rows': len(rows), 'exact_database_matches': exact,
            'mapping_basis': 'zero_based_video_index_to_ordered_gps_row; annotation interval [start,end)',
            'alternatives': candidates,
            'status': ('verified' if video_frames_verified else 'conditional_on_video_frame_parity') if valid else 'unresolved',
            'usable_for_confirmed_language_evaluation': valid and video_frames_verified,
            'warning': 'Window endpoints are not observed action onset/completion or instruction issue time.'}

def inventory(records, parser):
    counts, actions, examples, clips = Counter(), Counter(), {}, {}
    for record in records:
        if not record.instruction:
            counts['blank'] += 1
            continue
        parsed = parser(record.instruction)
        counts[parsed['status']] += 1
        group = clips.setdefault(record.clip_id, {'recording_id': record.recording_id, 'annotations': []})
        group['annotations'].append({'annotation_id': record.annotation_id,
                                     'instruction': record.instruction, 'parse': parsed,
                                     'start_frame': record.start_frame, 'end_frame': record.end_frame})
        if parsed['status'] == 'parsed':
            for stage in parsed['stages']:
                actions[stage['action']] += 1
        else:
            reason = parsed.get('reason', 'unknown')
            examples.setdefault(reason, [])
            if len(examples[reason]) < 12:
                examples[reason].append(record.instruction)
    return {'counts': dict(counts), 'parsed_actions': dict(actions),
            'unsupported_examples': examples, 'clips': clips,
            'split_unit': 'recording_id (all segments of a drive kept together)'}
