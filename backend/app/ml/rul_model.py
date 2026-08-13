from __future__ import annotations

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


def _synthetic_training_set(n: int = 200, seed: int = 42) -> tuple[np.ndarray, np.ndarray]:
    """Deterministic training set for RUL regression (not Math.random telemetry)."""
    rng = np.random.default_rng(seed)
    contact_resistance = rng.uniform(0.1, 2.5, size=n)
    touchdown_count = rng.uniform(1_000, 80_000, size=n)
    temp_drift = rng.uniform(0.0, 8.0, size=n)
    leak_current = rng.uniform(1e-9, 5e-7, size=n)
    X = np.column_stack([contact_resistance, touchdown_count, temp_drift, leak_current])
    # Lower health / RUL as wear features rise
    health = (
        100
        - 12 * contact_resistance
        - 0.0004 * touchdown_count
        - 3.5 * temp_drift
        - 2e7 * leak_current
    )
    health = np.clip(health, 5, 99)
    rul_days = health / 4.5
    return X, rul_days


class RulEstimator:
    def __init__(self) -> None:
        self.model: Pipeline | None = None

    def fit(self, seed: int = 42) -> "RulEstimator":
        X, y = _synthetic_training_set(seed=seed)
        self.model = Pipeline(
            steps=[
                ("scaler", StandardScaler()),
                ("gbr", GradientBoostingRegressor(random_state=seed, n_estimators=80)),
            ]
        )
        self.model.fit(X, y)
        return self

    def predict_health_and_rul(self, features: dict[str, float]) -> tuple[float, float]:
        if self.model is None:
            self.fit()
        assert self.model is not None
        x = np.array(
            [
                [
                    float(features.get("contact_resistance", 0.5)),
                    float(features.get("touchdown_count", 10000)),
                    float(features.get("temp_drift", 1.0)),
                    float(features.get("leak_current", 1e-8)),
                ]
            ]
        )
        rul = float(self.model.predict(x)[0])
        health = float(np.clip(rul * 4.5, 1, 99))
        return round(health, 1), round(rul, 1)
