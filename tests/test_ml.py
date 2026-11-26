"""Tests for lift dataset generation, Random Forest training, evaluation, and missing-data inference."""

from __future__ import annotations

import numpy as np

from ml.features import SENSOR_FEATURES, classify_risk_level
from ml.generate_dataset import TARGET_COLUMN, generate_historical_dataset
from ml.predict import LiftBreakdownPredictor
from ml.train_model import train_and_save_model


def test_dataset_generation_and_schema(tmp_path) -> None:
    ds_path = tmp_path / "hist.csv"
    df = generate_historical_dataset(output_path=ds_path, days=15, seed=123)
    assert ds_path.exists()
    assert len(df) > 1000
    for col in SENSOR_FEATURES:
        assert col in df.columns
    assert TARGET_COLUMN in df.columns
    assert set(df[TARGET_COLUMN].unique()).issubset({0, 1})
    assert df[SENSOR_FEATURES].isna().sum().sum() > 0


def test_training_evaluation_and_missing_value_inference(tmp_path) -> None:
    ds_path = tmp_path / "hist.csv"
    mdl_path = tmp_path / "model.joblib"
    mtr_path = tmp_path / "metrics.json"

    generate_historical_dataset(output_path=ds_path, days=25, seed=42)
    report = train_and_save_model(
        dataset_path=ds_path,
        model_path=mdl_path,
        metrics_path=mtr_path,
        seed=42,
        sync_db=False,
    )

    assert mdl_path.exists()
    assert mtr_path.exists()
    metrics = report["metrics"]
    for key in ("accuracy", "precision", "recall", "f1_score", "confusion_matrix", "feature_importance"):
        assert key in metrics
    assert 0.5 < metrics["accuracy"] <= 1.0
    assert 0.5 < metrics["recall"] <= 1.0
    assert len(metrics["feature_importance"]) == len(SENSOR_FEATURES)

    predictor = LiftBreakdownPredictor(model_path=mdl_path, metrics_path=mtr_path)
    predictor.load()
    assert predictor.is_loaded()

    healthy_partial = {
        "lift_id": "LIFT-01",
        "motor_temp": 52.0,
        "vibration_level": None,
        "door_cycle_time": 2.9,
        "motor_current": np.nan,
        "cabin_load": 0.0,
        "travel_time": 9.8,
    }
    res_healthy = predictor.predict_reading(healthy_partial)
    assert 0.0 <= res_healthy["breakdown_probability"] <= 1.0
    assert res_healthy["breakdown_probability"] < 0.5

    failing_reading = {
        "lift_id": "LIFT-01",
        "motor_temp": 88.5,
        "vibration_level": 5.6,
        "door_cycle_time": 6.1,
        "motor_current": 41.2,
        "cabin_load": 480.0,
        "travel_time": 17.5,
    }
    res_fail = predictor.predict_reading(failing_reading)
    assert res_fail["breakdown_probability"] >= 0.70
    assert res_fail["predicted_class"] == 1
    assert res_fail["risk_level"] in ("High", "Critical")


def test_risk_classification_boundaries() -> None:
    assert classify_risk_level(0.0) == "Low"
    assert classify_risk_level(0.39) == "Low"
    assert classify_risk_level(0.40) == "Medium"
    assert classify_risk_level(0.69) == "Medium"
    assert classify_risk_level(0.70) == "High"
    assert classify_risk_level(0.89) == "High"
    assert classify_risk_level(0.90) == "Critical"
