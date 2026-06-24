#!/usr/bin/env python3
"""Build every compact JSON artifact consumed by the Quarto site."""

from __future__ import annotations

import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analysis import (  # noqa: E402
    LOCALISATION_START,
    build_oblast_unions,
    build_raion_unions,
    counterfactual_savings,
    daily_metrics,
    load_alerts,
    load_boundary_index,
)
from src.forecast import build_hourly_load, forecast_snapshot  # noqa: E402

RAW_CSV = ROOT / "data/raw/official_data_en.csv"
ADMIN1 = ROOT / "data/geo/ukraine_admin1.geojson"
ADMIN2 = ROOT / "data/geo/ukraine_admin2.geojson"
OUTPUT = ROOT / "site-data"


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    boundaries = load_boundary_index(ADMIN1, ADMIN2)
    alerts, load_diagnostics = load_alerts(RAW_CSV, boundaries)
    print(f"Loaded {len(alerts):,} valid alert rows")

    oblast_unions = build_oblast_unions(alerts)
    raion_unions, raion_diagnostics = build_raion_unions(alerts, boundaries)
    print(f"Built canonical unions for {len(oblast_unions)} oblasts and {len(raion_unions)} raions")

    oblast_daily, oblast_totals = daily_metrics(oblast_unions)
    raion_daily, raion_totals = daily_metrics(raion_unions, start_date=LOCALISATION_START)
    write_json(
        OUTPUT / "history.json",
        {
            "oblast": oblast_daily,
            "raion": raion_daily,
            "oblast_totals": oblast_totals,
            "raion_totals": raion_totals,
            "metrics": ["count", "minutes", "longest", "night_minutes"],
            "first_date": min(oblast_daily),
            "last_date": max(oblast_daily),
            "raion_first_date": LOCALISATION_START.isoformat(),
        },
    )
    print(f"History covers {min(oblast_daily)} through {max(oblast_daily)}")

    savings = counterfactual_savings(raion_unions, boundaries)
    write_json(OUTPUT / "savings.json", savings)
    print(f"Counterfactual savings: {savings['national_saved_raion_minutes']:,.0f} raion-minutes")

    last_finished = alerts["finished_at"].max()
    hourly, forecast_diagnostics = build_hourly_load(
        raion_unions,
        boundaries,
        start=pd.Timestamp("2025-12-01", tz="UTC"),
        last_finished_at=last_finished,
    )
    forecast = forecast_snapshot(hourly)
    forecast["diagnostics"] = forecast_diagnostics
    forecast["snapshot_generated_at"] = datetime.now(UTC).isoformat()
    forecast["limitation"] = (
        "Static snapshot forecast. The repository has no approved live API token; "
        "predictions are anchored to the final complete hour in the downloaded CSV."
    )
    write_json(OUTPUT / "forecast.json", forecast)
    print(f"Forecast origin: {forecast['origin']}")

    metadata = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source_csv": str(RAW_CSV.relative_to(ROOT)),
        "load_diagnostics": load_diagnostics,
        "raion_diagnostics": raion_diagnostics,
        "forecast_diagnostics": forecast_diagnostics,
        "definitions": {
            "oblast_minutes": "Union minutes during which any reported alert was active inside an oblast.",
            "raion_minutes": "Sum of unique alert minutes across canonical raion coverage.",
            "counterfactual": "Every local alert is expanded to every raion in its parent oblast.",
            "forecast_load": "Share of monitored raion-minutes under alert during an hour.",
        },
    }
    write_json(OUTPUT / "metadata.json", metadata)

    shutil.copy2(ADMIN1, OUTPUT / "ukraine_admin1.geojson")
    shutil.copy2(ADMIN2, OUTPUT / "ukraine_admin2.geojson")
    print(f"Wrote site artifacts to {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
