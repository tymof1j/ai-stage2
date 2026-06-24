"""Short-horizon snapshot forecasting for national alert-system load."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .analysis import BoundaryIndex, KYIV_TZ
from .intervals import allocate_to_hours


@dataclass
class RidgeModel:
    mean: np.ndarray
    scale: np.ndarray
    beta: np.ndarray

    def predict(self, features: np.ndarray) -> np.ndarray:
        standardized = (features - self.mean) / self.scale
        design = np.column_stack([np.ones(len(standardized)), standardized])
        return design @ self.beta


def fit_ridge(features: np.ndarray, target: np.ndarray, alpha: float) -> RidgeModel:
    """Fit a dependency-free standardized ridge regression."""

    mean = features.mean(axis=0)
    scale = features.std(axis=0)
    scale[scale == 0] = 1
    standardized = (features - mean) / scale
    design = np.column_stack([np.ones(len(standardized)), standardized])
    penalty = np.eye(design.shape[1]) * alpha
    penalty[0, 0] = 0
    beta = np.linalg.pinv(design.T @ design + penalty) @ design.T @ target
    return RidgeModel(mean=mean, scale=scale, beta=beta)


def build_hourly_load(
    raion_unions: dict[str, list[tuple[pd.Timestamp, pd.Timestamp]]],
    boundaries: BoundaryIndex,
    start: pd.Timestamp,
    last_finished_at: pd.Timestamp,
) -> tuple[pd.DataFrame, dict]:
    """Build hourly national exposure from canonical raion intervals.

    Crimea, Sevastopol and Luhanska are excluded from the denominator because
    the source does not represent their permanent-alert regimes as ordinary
    intervals. The Chornobyl Exclusion Zone remains part of Kyivska oblast.
    """

    excluded_adm1_names = {"Autonomous Republic of Crimea", "Sevastopol", "Luhanska"}
    eligible = {
        code
        for code, adm1 in boundaries.adm2_adm1_by_code.items()
        if boundaries.adm1_name_by_code.get(adm1) not in excluded_adm1_names
        and code in raion_unions
    }
    if not eligible:
        raise ValueError("No eligible raions for forecasting")

    last_complete_hour = last_finished_at.floor("h") - pd.Timedelta(hours=1)
    hourly_minutes: dict[pd.Timestamp, float] = {}
    hourly_starts: dict[pd.Timestamp, int] = {}
    hourly_ends: dict[pd.Timestamp, int] = {}

    for code in eligible:
        intervals = [
            (max(interval_start, start), interval_end)
            for interval_start, interval_end in raion_unions[code]
            if interval_end > start and interval_start < last_complete_hour + pd.Timedelta(hours=1)
        ]
        for hour, minutes in allocate_to_hours(intervals).items():
            if start <= hour <= last_complete_hour:
                hourly_minutes[hour] = hourly_minutes.get(hour, 0.0) + minutes
        for interval_start, interval_end in intervals:
            start_hour = interval_start.floor("h")
            end_hour = interval_end.floor("h")
            if start <= start_hour <= last_complete_hour:
                hourly_starts[start_hour] = hourly_starts.get(start_hour, 0) + 1
            if start <= end_hour <= last_complete_hour:
                hourly_ends[end_hour] = hourly_ends.get(end_hour, 0) + 1

    index = pd.date_range(start=start.floor("h"), end=last_complete_hour, freq="h", tz="UTC")
    denominator = len(eligible) * 60
    frame = pd.DataFrame(index=index)
    frame["load"] = [hourly_minutes.get(hour, 0.0) / denominator for hour in index]
    frame["starts"] = [hourly_starts.get(hour, 0) / len(eligible) for hour in index]
    frame["ends"] = [hourly_ends.get(hour, 0) / len(eligible) for hour in index]
    diagnostics = {
        "eligible_raions": len(eligible),
        "first_hour": index.min().isoformat(),
        "last_complete_hour": index.max().isoformat(),
        "last_finished_at": last_finished_at.isoformat(),
        "excluded_adm1_names": sorted(excluded_adm1_names),
    }
    return frame, diagnostics


def build_features(hourly: pd.DataFrame) -> pd.DataFrame:
    """Construct strictly lagged/autoregressive features available at origin time."""

    features = pd.DataFrame(index=hourly.index)
    for lag in range(0, 25):
        features[f"load_lag_{lag}"] = hourly["load"].shift(lag)
    for lag in (48, 72, 168):
        features[f"load_lag_{lag}"] = hourly["load"].shift(lag)
    for window in (3, 6, 12, 24, 72, 168):
        features[f"load_mean_{window}"] = hourly["load"].rolling(window).mean()
    for window in (6, 24, 168):
        features[f"load_std_{window}"] = hourly["load"].rolling(window).std().fillna(0)
    for name in ("starts", "ends"):
        features[f"{name}_now"] = hourly[name]
        features[f"{name}_mean_6"] = hourly[name].rolling(6).mean()
        features[f"{name}_mean_24"] = hourly[name].rolling(24).mean()

    local_index = hourly.index.tz_convert(KYIV_TZ)
    hour_angle = 2 * np.pi * local_index.hour / 24
    week_angle = 2 * np.pi * local_index.dayofweek / 7
    features["hour_sin"] = np.sin(hour_angle)
    features["hour_cos"] = np.cos(hour_angle)
    features["weekday_sin"] = np.sin(week_angle)
    features["weekday_cos"] = np.cos(week_angle)
    return features


def _mae(actual: np.ndarray, predicted: np.ndarray) -> float:
    return float(np.mean(np.abs(actual - predicted)))


def forecast_snapshot(hourly: pd.DataFrame, max_horizon: int = 6) -> dict:
    """Fit direct ridge models, benchmark them, and forecast horizons 1..6."""

    features = build_features(hourly)
    origins = features.dropna().index
    if len(origins) < 24 * 100:
        raise ValueError("At least 100 days of complete hourly features are required")

    last_origin = origins.max()
    test_start = last_origin - pd.Timedelta(days=30)
    validation_start = test_start - pd.Timedelta(days=30)
    feature_columns = list(features.columns)
    alpha_grid = (0.1, 1.0, 10.0, 100.0)
    predictions: list[dict] = []
    evaluations: list[dict] = []

    for horizon in range(1, max_horizon + 1):
        target = hourly["load"].shift(-horizon).rename("target")
        dataset = features.join(target).dropna()
        train = dataset[dataset.index < validation_start]
        validation = dataset[(dataset.index >= validation_start) & (dataset.index < test_start)]
        test = dataset[dataset.index >= test_start]
        if min(len(train), len(validation), len(test)) == 0:
            raise ValueError("Temporal split produced an empty partition")

        x_train = train[feature_columns].to_numpy(float)
        y_train = train["target"].to_numpy(float)
        x_validation = validation[feature_columns].to_numpy(float)
        y_validation = validation["target"].to_numpy(float)

        candidates = []
        for alpha in alpha_grid:
            candidate = fit_ridge(x_train, y_train, alpha)
            predicted = np.clip(candidate.predict(x_validation), 0, 1)
            candidates.append((alpha, _mae(y_validation, predicted), candidate, predicted))
        alpha, validation_mae, selected, validation_predicted = min(candidates, key=lambda item: item[1])
        validation_residual = np.abs(y_validation - validation_predicted)
        interval_radius = float(np.quantile(validation_residual, 0.90))

        development = dataset[dataset.index < test_start]
        deployed = fit_ridge(
            development[feature_columns].to_numpy(float), development["target"].to_numpy(float), alpha
        )
        x_test = test[feature_columns].to_numpy(float)
        y_test = test["target"].to_numpy(float)
        model_test = np.clip(deployed.predict(x_test), 0, 1)
        persistence_test = test["load_lag_0"].to_numpy(float)
        seasonal_lag = 24 - horizon
        seasonal_test = test[f"load_lag_{seasonal_lag}"].to_numpy(float)

        model_mae = _mae(y_test, model_test)
        persistence_mae = _mae(y_test, persistence_test)
        seasonal_mae = _mae(y_test, seasonal_test)
        baseline_name, baseline_mae = min(
            (("persistence", persistence_mae), ("same-hour-yesterday", seasonal_mae)),
            key=lambda item: item[1],
        )
        skill = 1 - model_mae / baseline_mae if baseline_mae else 0

        final_dataset = dataset[dataset.index <= last_origin]
        final_model = fit_ridge(
            final_dataset[feature_columns].to_numpy(float),
            final_dataset["target"].to_numpy(float),
            alpha,
        )
        current_features = features.loc[[last_origin], feature_columns].to_numpy(float)
        point = float(np.clip(final_model.predict(current_features)[0], 0, 1))

        predictions.append(
            {
                "horizon": horizon,
                "timestamp": (last_origin + pd.Timedelta(hours=horizon)).isoformat(),
                "point": round(point, 4),
                "lower": round(max(0, point - interval_radius), 4),
                "upper": round(min(1, point + interval_radius), 4),
            }
        )
        evaluations.append(
            {
                "horizon": horizon,
                "alpha": alpha,
                "validation_mae": round(validation_mae, 5),
                "model_mae": round(model_mae, 5),
                "persistence_mae": round(persistence_mae, 5),
                "seasonal_mae": round(seasonal_mae, 5),
                "best_baseline": baseline_name,
                "skill_vs_best_baseline": round(skill, 4),
                "test_observations": len(test),
            }
        )

    history = [
        {"timestamp": timestamp.isoformat(), "load": round(float(value), 4)}
        for timestamp, value in hourly.loc[last_origin - pd.Timedelta(days=14) : last_origin, "load"].items()
    ]
    reference = hourly.loc[hourly.index < validation_start, "load"]
    thresholds = np.quantile(reference, [0.25, 0.50, 0.75])
    outlook_mean = float(np.mean([row["point"] for row in predictions if row["horizon"] >= 3]))
    outlook_index = int(np.searchsorted(thresholds, outlook_mean, side="right"))
    outlook_labels = ("Низьке", "Помірне", "Середньо-високе", "Високе")
    return {
        "origin": last_origin.isoformat(),
        "current_load": round(float(hourly.loc[last_origin, "load"]), 4),
        "predictions": predictions,
        "evaluations": evaluations,
        "outlook": {
            "label": outlook_labels[outlook_index],
            "level": ("low", "moderate", "medium-high", "high")[outlook_index],
            "mean_load": round(outlook_mean, 4),
            "reference_quartiles": [round(float(value), 4) for value in thresholds],
            "horizons": [3, 4, 5, 6],
        },
        "history": history,
        "validation_start": validation_start.isoformat(),
        "test_start": test_start.isoformat(),
        "method": "direct standardized ridge regression with autoregressive and calendar features",
    }
