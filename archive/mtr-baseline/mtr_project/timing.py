"""Integer-microsecond, half-open windows for recorded observations."""
import math


def interval_bounds(first_timestamp_us, start_seconds=0., duration=None):
    if not math.isfinite(start_seconds) or start_seconds < 0:
        raise ValueError('Start must be finite and nonnegative')
    if duration is not None and (not math.isfinite(duration) or duration <= 0):
        raise ValueError('Duration must be finite and positive')
    start = int(first_timestamp_us) + round(start_seconds * 1_000_000)
    end = None if duration is None else start + round(duration * 1_000_000)
    if end is not None and end <= start:
        raise ValueError('Duration must span at least one microsecond')
    return start, end


def within_interval(timestamp_us, bounds):
    start, end = bounds
    return timestamp_us >= start and (end is None or timestamp_us < end)
