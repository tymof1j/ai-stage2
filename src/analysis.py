"""Load, normalize and aggregate the official alert interval snapshot."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from .intervals import Interval, interval_minutes, merge_intervals, night_minutes, split_by_local_day

KYIV_TZ = "Europe/Kyiv"
LOCALISATION_START = date(2025, 12, 1)

RAION_ALIASES = {
    "Chervonohradskyi": "Sheptytskyi",
    "Krasnohradskyi": "Berestynskyi",
    "Volodymyr-Volynskyi": "Volodymyrskyi",
}


@dataclass(frozen=True)
class BoundaryIndex:
    adm1_code_by_name: dict[str, str]
    adm1_uk_by_code: dict[str, str]
    adm1_name_by_code: dict[str, str]
    adm2_code_by_names: dict[tuple[str, str], str]
    adm2_uk_by_code: dict[str, str]
    adm2_name_by_code: dict[str, str]
    adm2_adm1_by_code: dict[str, str]
    adm2_codes_by_adm1: dict[str, tuple[str, ...]]


def _dataset_oblast_name(value: str) -> str:
    if value == "Kyiv City":
        return "Kyiv"
    return value.removesuffix(" oblast")


def _dataset_raion_name(value: str | None) -> str | None:
    if value is None or pd.isna(value):
        return None
    normalized = str(value).removesuffix(" raion")
    return RAION_ALIASES.get(normalized, normalized)


def load_boundary_index(admin1_path: Path, admin2_path: Path) -> BoundaryIndex:
    """Create name and hierarchy lookup tables from simplified OCHA GeoJSON."""

    admin1 = json.loads(admin1_path.read_text())
    admin2 = json.loads(admin2_path.read_text())

    adm1_code_by_name: dict[str, str] = {}
    adm1_uk_by_code: dict[str, str] = {}
    adm1_name_by_code: dict[str, str] = {}
    for feature in admin1["features"]:
        props = feature["properties"]
        code = props["adm1_pcode"]
        adm1_code_by_name[props["adm1_name"]] = code
        adm1_uk_by_code[code] = props["adm1_name1"]
        adm1_name_by_code[code] = props["adm1_name"]

    adm2_code_by_names: dict[tuple[str, str], str] = {}
    adm2_uk_by_code: dict[str, str] = {}
    adm2_name_by_code: dict[str, str] = {}
    adm2_adm1_by_code: dict[str, str] = {}
    grouped: dict[str, list[str]] = defaultdict(list)
    for feature in admin2["features"]:
        props = feature["properties"]
        code = props["adm2_pcode"]
        adm1_code = props["adm1_pcode"]
        adm2_code_by_names[(props["adm1_name"], props["adm2_name"])] = code
        adm2_uk_by_code[code] = props["adm2_name1"]
        adm2_name_by_code[code] = props["adm2_name"]
        adm2_adm1_by_code[code] = adm1_code
        grouped[adm1_code].append(code)

    return BoundaryIndex(
        adm1_code_by_name=adm1_code_by_name,
        adm1_uk_by_code=adm1_uk_by_code,
        adm1_name_by_code=adm1_name_by_code,
        adm2_code_by_names=adm2_code_by_names,
        adm2_uk_by_code=adm2_uk_by_code,
        adm2_name_by_code=adm2_name_by_code,
        adm2_adm1_by_code=adm2_adm1_by_code,
        adm2_codes_by_adm1={key: tuple(sorted(value)) for key, value in grouped.items()},
    )


def load_alerts(path: Path, boundaries: BoundaryIndex) -> tuple[pd.DataFrame, dict]:
    """Read the CSV, validate intervals and attach OCHA administrative codes."""

    frame = pd.read_csv(path, parse_dates=["started_at", "finished_at"])
    input_rows = len(frame)
    frame = frame.dropna(subset=["oblast", "started_at", "finished_at"]).copy()
    frame = frame[frame["finished_at"] > frame["started_at"]].copy()
    frame["oblast_name"] = frame["oblast"].map(_dataset_oblast_name)
    frame["adm1_pcode"] = frame["oblast_name"].map(boundaries.adm1_code_by_name)
    frame["raion_name"] = frame["raion"].map(_dataset_raion_name)
    frame["adm2_pcode"] = [
        boundaries.adm2_code_by_names.get((oblast, raion)) if raion else None
        for oblast, raion in zip(frame["oblast_name"], frame["raion_name"], strict=False)
    ]

    unmatched_oblasts = sorted(frame.loc[frame["adm1_pcode"].isna(), "oblast"].unique())
    unmatched_raions = sorted(
        frame.loc[frame["raion"].notna() & frame["adm2_pcode"].isna(), "raion"].unique()
    )
    diagnostics = {
        "input_rows": input_rows,
        "valid_rows": len(frame),
        "invalid_rows": input_rows - len(frame),
        "unmatched_oblasts": unmatched_oblasts,
        "unmatched_raions": unmatched_raions,
        "first_started_at": frame["started_at"].min().isoformat(),
        "last_finished_at": frame["finished_at"].max().isoformat(),
        "levels": {str(k): int(v) for k, v in frame["level"].value_counts().items()},
    }
    if unmatched_oblasts:
        raise ValueError(f"Unmatched oblast names: {unmatched_oblasts}")
    return frame, diagnostics


def build_oblast_unions(frame: pd.DataFrame) -> dict[str, list[Interval]]:
    """Union all reported alert locations within each oblast."""

    result: dict[str, list[Interval]] = {}
    for code, group in frame.groupby("adm1_pcode", observed=True):
        result[str(code)] = merge_intervals(zip(group["started_at"], group["finished_at"], strict=False))
    return result


def build_raion_unions(
    frame: pd.DataFrame, boundaries: BoundaryIndex
) -> tuple[dict[str, list[Interval]], dict]:
    """Project every alert to a canonical raion coverage representation.

    Oblast alerts cover every raion in that oblast. Raion alerts cover their
    named raion. Hromada alerts are conservatively aggregated to their parent
    raion because this project does not use admin-3 geometry.
    """

    intervals: dict[str, list[Interval]] = defaultdict(list)
    skipped = Counter()
    for row in frame.itertuples(index=False):
        interval = (row.started_at, row.finished_at)
        if row.level == "oblast":
            codes = boundaries.adm2_codes_by_adm1.get(row.adm1_pcode, ())
            if not codes:
                skipped["oblast_without_raions"] += 1
            for code in codes:
                intervals[code].append(interval)
        elif row.adm2_pcode:
            intervals[row.adm2_pcode].append(interval)
        else:
            skipped[f"unmapped_{row.level}"] += 1

    merged = {code: merge_intervals(values) for code, values in intervals.items()}
    return merged, {"skipped": dict(skipped), "mapped_raions": len(merged)}


def daily_metrics(
    unions: dict[str, list[Interval]],
    start_date: date | None = None,
) -> tuple[dict[str, dict[str, list[float]]], dict[str, dict[str, float]]]:
    """Create compact date-indexed metrics and per-region totals.

    Metric arrays are ``[episode_count, unique_minutes, longest_segment,
    night_minutes]``.
    """

    by_date: dict[str, dict[str, list[float]]] = defaultdict(dict)
    totals: dict[str, dict[str, float]] = {}

    for code, intervals in unions.items():
        starts = Counter(
            start.tz_convert(KYIV_TZ).date()
            for start, _ in intervals
            if start_date is None or start.tz_convert(KYIV_TZ).date() >= start_date
        )
        split = split_by_local_day(intervals, KYIV_TZ)
        region_minutes = 0.0
        region_episodes = 0
        for day, segments in split.items():
            if start_date is not None and day < start_date:
                continue
            minutes = interval_minutes(segments)
            longest = max((end - start).total_seconds() / 60 for start, end in segments)
            nights = night_minutes(segments)
            count = int(starts.get(day, 0))
            by_date[day.isoformat()][code] = [
                count,
                round(minutes, 1),
                round(longest, 1),
                round(nights, 1),
            ]
            region_minutes += minutes
            region_episodes += count
        totals[code] = {
            "episodes": region_episodes,
            "minutes": round(region_minutes, 1),
        }
    return dict(sorted(by_date.items())), totals


def counterfactual_savings(
    raion_unions: dict[str, list[Interval]],
    boundaries: BoundaryIndex,
    start_date: date = LOCALISATION_START,
) -> dict:
    """Compare targeted raion coverage with an oblast-wide counterfactual."""

    actual_daily: dict[tuple[str, date], float] = defaultdict(float)
    raion_daily_cache: dict[str, dict[date, list[Interval]]] = {}
    for raion_code, intervals in raion_unions.items():
        adm1 = boundaries.adm2_adm1_by_code[raion_code]
        split = split_by_local_day(intervals, KYIV_TZ)
        filtered = {day: segments for day, segments in split.items() if day >= start_date}
        raion_daily_cache[raion_code] = filtered
        for day, segments in filtered.items():
            actual_daily[(adm1, day)] += interval_minutes(segments)

    oblast_union_daily: dict[tuple[str, date], float] = {}
    for adm1, raion_codes in boundaries.adm2_codes_by_adm1.items():
        all_intervals = [
            interval
            for code in raion_codes
            for interval in raion_unions.get(code, [])
        ]
        if not all_intervals:
            continue
        for day, segments in split_by_local_day(all_intervals, KYIV_TZ).items():
            if day >= start_date:
                oblast_union_daily[(adm1, day)] = interval_minutes(segments)

    daily: list[dict] = []
    totals: dict[str, dict[str, float]] = defaultdict(
        lambda: {"actual": 0.0, "counterfactual": 0.0, "saved": 0.0, "days": 0}
    )
    all_keys = sorted(set(actual_daily) | set(oblast_union_daily), key=lambda item: (item[1], item[0]))
    for adm1, day in all_keys:
        n_raions = len(boundaries.adm2_codes_by_adm1.get(adm1, ()))
        if n_raions == 0:
            continue
        actual = actual_daily.get((adm1, day), 0.0)
        counter = oblast_union_daily.get((adm1, day), 0.0) * n_raions
        saved = max(0.0, counter - actual)
        daily.append(
            {
                "d": day.isoformat(),
                "id": adm1,
                "a": round(actual, 1),
                "c": round(counter, 1),
                "s": round(saved, 1),
                "n": n_raions,
            }
        )
        totals[adm1]["actual"] += actual
        totals[adm1]["counterfactual"] += counter
        totals[adm1]["saved"] += saved
        totals[adm1]["days"] += 1

    totals_output: list[dict] = []
    for adm1, values in totals.items():
        n_raions = len(boundaries.adm2_codes_by_adm1.get(adm1, ()))
        counter = values["counterfactual"]
        totals_output.append(
            {
                "id": adm1,
                "name": boundaries.adm1_uk_by_code.get(adm1, adm1),
                "n": n_raions,
                "actual": round(values["actual"], 1),
                "counterfactual": round(counter, 1),
                "saved": round(values["saved"], 1),
                "saved_pct": round(100 * values["saved"] / counter, 1) if counter else 0,
                "equivalent_hours": round(values["saved"] / max(n_raions, 1) / 60, 1),
            }
        )
    totals_output.sort(key=lambda item: item["saved"], reverse=True)

    national_by_day: dict[str, dict[str, float]] = defaultdict(
        lambda: {"actual": 0.0, "counterfactual": 0.0, "saved": 0.0}
    )
    for row in daily:
        bucket = national_by_day[row["d"]]
        bucket["actual"] += row["a"]
        bucket["counterfactual"] += row["c"]
        bucket["saved"] += row["s"]

    cumulative = 0.0
    national_daily = []
    for day, values in sorted(national_by_day.items()):
        cumulative += values["saved"]
        national_daily.append(
            {
                "d": day,
                "a": round(values["actual"], 1),
                "c": round(values["counterfactual"], 1),
                "s": round(values["saved"], 1),
                "cum": round(cumulative, 1),
            }
        )

    return {
        "start_date": start_date.isoformat(),
        "daily": daily,
        "national_daily": national_daily,
        "totals": totals_output,
        "national_saved_raion_minutes": round(sum(item["saved"] for item in totals_output), 1),
        "national_counterfactual_raion_minutes": round(
            sum(item["counterfactual"] for item in totals_output), 1
        ),
    }
