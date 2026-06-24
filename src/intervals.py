"""Interval algebra used by every analytical module.

All computation uses timezone-aware timestamps. Intervals follow the half-open
convention ``[start, end)`` so adjacent alerts can be merged without double
counting a boundary instant.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date

import pandas as pd

Interval = tuple[pd.Timestamp, pd.Timestamp]


def merge_intervals(intervals: Iterable[Interval]) -> list[Interval]:
    """Return the sorted union of overlapping or directly adjacent intervals."""

    valid = sorted((start, end) for start, end in intervals if end > start)
    if not valid:
        return []

    merged: list[list[pd.Timestamp]] = [[valid[0][0], valid[0][1]]]
    for start, end in valid[1:]:
        previous = merged[-1]
        if start <= previous[1]:
            if end > previous[1]:
                previous[1] = end
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def intersect_interval(interval: Interval, window: Interval) -> Interval | None:
    """Return the intersection of two half-open intervals, if non-empty."""

    start = max(interval[0], window[0])
    end = min(interval[1], window[1])
    return (start, end) if end > start else None


def interval_minutes(intervals: Iterable[Interval]) -> float:
    """Return union duration in minutes."""

    return sum((end - start).total_seconds() / 60 for start, end in merge_intervals(intervals))


def split_by_local_day(
    intervals: Iterable[Interval], timezone: str = "Europe/Kyiv"
) -> dict[date, list[Interval]]:
    """Split UTC intervals at local midnight and return local-time segments."""

    result: dict[date, list[Interval]] = defaultdict(list)
    for start_utc, end_utc in merge_intervals(intervals):
        start = start_utc.tz_convert(timezone)
        end = end_utc.tz_convert(timezone)
        cursor = start
        while cursor < end:
            next_midnight = cursor.normalize() + pd.DateOffset(days=1)
            segment_end = min(end, next_midnight)
            result[cursor.date()].append((cursor, segment_end))
            cursor = segment_end
    return dict(result)


def night_minutes(intervals: Iterable[Interval]) -> float:
    """Minutes within 22:00–06:00 for already day-split local intervals."""

    total = 0.0
    for start, end in intervals:
        day_start = start.normalize()
        windows = (
            (day_start, day_start + pd.Timedelta(hours=6)),
            (day_start + pd.Timedelta(hours=22), day_start + pd.DateOffset(days=1)),
        )
        for window in windows:
            overlap = intersect_interval((start, end), window)
            if overlap:
                total += (overlap[1] - overlap[0]).total_seconds() / 60
    return total


def allocate_to_hours(intervals: Iterable[Interval]) -> dict[pd.Timestamp, float]:
    """Allocate union duration to UTC hour buckets."""

    result: dict[pd.Timestamp, float] = defaultdict(float)
    for start, end in merge_intervals(intervals):
        cursor = start
        while cursor < end:
            hour = cursor.floor("h")
            segment_end = min(end, hour + pd.Timedelta(hours=1))
            result[hour] += (segment_end - cursor).total_seconds() / 60
            cursor = segment_end
    return dict(result)

