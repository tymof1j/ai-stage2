import unittest

import pandas as pd

from src.intervals import allocate_to_hours, interval_minutes, merge_intervals, split_by_local_day


def ts(value: str) -> pd.Timestamp:
    return pd.Timestamp(value, tz="UTC")


class IntervalTests(unittest.TestCase):
    def test_merges_overlaps_and_adjacency(self):
        intervals = [
            (ts("2026-01-01 00:00"), ts("2026-01-01 01:00")),
            (ts("2026-01-01 00:30"), ts("2026-01-01 02:00")),
            (ts("2026-01-01 02:00"), ts("2026-01-01 02:30")),
        ]
        self.assertEqual(merge_intervals(intervals), [(ts("2026-01-01 00:00"), ts("2026-01-01 02:30"))])

    def test_union_minutes_does_not_double_count(self):
        intervals = [
            (ts("2026-01-01 00:00"), ts("2026-01-01 01:00")),
            (ts("2026-01-01 00:30"), ts("2026-01-01 01:30")),
        ]
        self.assertEqual(interval_minutes(intervals), 90)

    def test_split_uses_kyiv_midnight(self):
        intervals = [(ts("2026-01-01 21:30"), ts("2026-01-01 22:30"))]
        split = split_by_local_day(intervals)
        self.assertEqual(sorted(split), [pd.Timestamp("2026-01-01").date(), pd.Timestamp("2026-01-02").date()])
        self.assertEqual([interval_minutes(split[day]) for day in sorted(split)], [30, 30])

    def test_hour_allocation(self):
        intervals = [(ts("2026-01-01 00:45"), ts("2026-01-01 02:15"))]
        allocated = allocate_to_hours(intervals)
        self.assertEqual(list(allocated.values()), [15, 60, 15])


if __name__ == "__main__":
    unittest.main()
