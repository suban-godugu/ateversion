from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.ml.predictive_maintenance.models import FEATURE_NAMES, TelemetryFeature

MODEL_DIR = Path(__file__).resolve().parent / "artifacts"
MODEL_PATH = MODEL_DIR / "pm_bundle.joblib"


def _physics_targets(X: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Deterministic physics-inspired labels for supervised training.
    Not browser RNG — fixed seed corpus for model fit only.
    Columns match FEATURE_NAMES.
    """
    (
        test_failures,
        parametric_drift,
        contact_resistance,
        temperature,
        voltage_deviation,
        current_deviation,
        cycle_count,
        historical_failures,
        maintenance_events,
        tester_utilization,
    ) = [X[:, i] for i in range(10)]

    wear = (
        0.35 * np.clip(contact_resistance / 2.5, 0, 1)
        + 0.15 * np.clip(parametric_drift / 8.0, 0, 1)
        + 0.12 * np.clip(test_failures / 40.0, 0, 1)
        + 0.10 * np.clip(cycle_count / 80000.0, 0, 1)
        + 0.08 * np.clip(historical_failures / 20.0, 0, 1)
        + 0.08 * np.clip(temperature / 85.0, 0, 1)
        + 0.06 * np.clip(voltage_deviation / 0.15, 0, 1)
        + 0.06 * np.clip(current_deviation / 0.2, 0, 1)
    )
    # Prior maintenance reduces wear signal
    wear = np.clip(wear - 0.04 * np.clip(maintenance_events / 10.0, 0, 1), 0, 1)
    utilization_stress = 0.05 * np.clip(tester_utilization, 0, 1)
    wear = np.clip(wear + utilization_stress, 0, 1)

    health = np.clip(100.0 * (1.0 - wear), 1.0, 99.5)
    rul_days = np.clip(health / 4.2 - 2.0 * wear * 5.0, 0.5, 45.0)
    # Logistic-style failure probability from wear
    failure_prob = 1.0 / (1.0 + np.exp(-8.0 * (wear - 0.45)))
    failure_prob = np.clip(failure_prob, 0.01, 0.99)
    return health, rul_days, failure_prob


def build_training_corpus(n: int = 600, seed: int = 42) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    X = np.column_stack(
        [
            rng.uniform(0, 50, n),  # test_failures
            rng.uniform(0, 10, n),  # parametric_drift
            rng.uniform(0.1, 2.8, n),  # contact_resistance
            rng.uniform(20, 95, n),  # temperature
            rng.uniform(0, 0.2, n),  # voltage_deviation
            rng.uniform(0, 0.25, n),  # current_deviation
            rng.uniform(500, 90000, n),  # cycle_count
            rng.uniform(0, 25, n),  # historical_failures
            rng.uniform(0, 12, n),  # maintenance_events
            rng.uniform(0.2, 1.0, n),  # tester_utilization
        ]
    )
    health, rul, fail_p = _physics_targets(X)
    return X, health, rul, fail_p


class PredictiveMaintenanceModel:
    """
    sklearn ensemble:
      - health_score regressor
      - rul_days regressor
      - failure_probability classifier on binned risk + calibrated regressor
    """

    def __init__(self) -> None:
        self.health_model: Pipeline | None = None
        self.rul_model: Pipeline | None = None
        self.fail_model: Pipeline | None = None
        self.available = False
        self.feature_names = FEATURE_NAMES

    def fit(self, seed: int = 42) -> "PredictiveMaintenanceModel":
        X, health, rul, fail_p = build_training_corpus(seed=seed)
        fail_label = (fail_p >= 0.5).astype(int)

        self.health_model = Pipeline(
            [
                ("scaler", StandardScaler()),
                ("gbr", GradientBoostingRegressor(random_state=seed, n_estimators=120)),
            ]
        )
        self.rul_model = Pipeline(
            [
                ("scaler", StandardScaler()),
                ("gbr", GradientBoostingRegressor(random_state=seed, n_estimators=120)),
            ]
        )
        self.fail_model = Pipeline(
            [
                ("scaler", StandardScaler()),
                ("gbc", GradientBoostingClassifier(random_state=seed, n_estimators=120)),
            ]
        )
        self.health_model.fit(X, health)
        self.rul_model.fit(X, rul)
        self.fail_model.fit(X, fail_label)
        # Store soft failure probability via physics blend with classifier confidence
        self._fail_soft = fail_p  # for documentation only
        self.available = True
        return self

    def save(self, path: Path | None = None) -> Path:
        path = path or MODEL_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(
            {
                "health": self.health_model,
                "rul": self.rul_model,
                "fail": self.fail_model,
                "features": self.feature_names,
            },
            path,
        )
        return path

    def load(self, path: Path | None = None) -> bool:
        path = path or MODEL_PATH
        if not path.exists():
            self.available = False
            return False
        try:
            bundle = joblib.load(path)
            self.health_model = bundle["health"]
            self.rul_model = bundle["rul"]
            self.fail_model = bundle["fail"]
            self.feature_names = bundle.get("features", FEATURE_NAMES)
            self.available = True
            return True
        except Exception:
            self.available = False
            return False

    def ensure_ready(self) -> bool:
        if self.available and self.health_model is not None:
            return True
        if self.load():
            return True
        try:
            self.fit().save()
            return True
        except Exception:
            self.available = False
            return False

    def predict(self, features: TelemetryFeature) -> dict[str, float | None]:
        if not self.ensure_ready():
            return {
                "health_score": None,
                "rul_days": None,
                "failure_probability": None,
                "confidence": None,
            }

        assert self.health_model and self.rul_model and self.fail_model
        x = np.array([features.as_vector()], dtype=float)
        health = float(np.clip(self.health_model.predict(x)[0], 0.0, 100.0))
        rul = float(np.clip(self.rul_model.predict(x)[0], 0.0, 60.0))
        # Classifier probability of "at risk" class
        proba = self.fail_model.predict_proba(x)[0]
        # class 1 = elevated failure risk
        fail_p = float(proba[1]) if len(proba) > 1 else float(proba[0])
        # Confidence from classifier margin + feature completeness
        margin = abs(fail_p - 0.5) * 2.0
        confidence = float(np.clip(0.55 + 0.4 * margin, 0.5, 0.98))

        return {
            "health_score": round(health, 2),
            "rul_days": round(rul, 2),
            "failure_probability": round(fail_p, 4),
            "confidence": round(confidence, 3),
        }


# Process-wide singleton
_model: PredictiveMaintenanceModel | None = None


def get_model() -> PredictiveMaintenanceModel:
    global _model
    if _model is None:
        _model = PredictiveMaintenanceModel()
        _model.ensure_ready()
    return _model
