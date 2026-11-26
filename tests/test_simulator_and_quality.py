"""Tests for lift simulator, quality validation, zero vs missing distinction, and drift detection."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.services.data_quality import detect_sensor_drift, evaluate_reading_quality
from ml.predict import LiftBreakdownPredictor
from simulator.sensor_generator import LiftSensorSimulator


def test_missing_vs_genuine_zero_distinction() -> None:
    reading = {
        "lift_id": "LIFT-01",
        "motor_temp": 52.4,
        "vibration_level": 1.15,
        "door_cycle_time": None,  # Missing
        "motor_current": 16.5,
        "cabin_load": 0.0,        # Genuine empty cabin (0.0 kg), NOT missing!
        "travel_time": 9.8,
    }
    q = evaluate_reading_quality(reading)
    assert q["is_missing_any"] is True
    assert q["missing_fields"] == ["door_cycle_time"]
    assert q["cabin_load"] == 0.0
    assert "cabin_load" not in q["missing_fields"]
    assert q["quality_status"] == "missing_values"


def test_out_of_range_detection() -> None:
    reading = {
        "lift_id": "LIFT-01",
        "motor_temp": 210.0,
        "vibration_level": 1.1,
        "door_cycle_time": 2.9,
        "motor_current": 16.0,
        "cabin_load": 320.0,
        "travel_time": 10.0,
    }
    q = evaluate_reading_quality(reading)
    assert q["quality_status"] == "out_of_range"
    assert "Motor Temperature" in q["quality_notes"]


def test_simulator_and_drift_detection(trained_artifacts) -> None:
    sim = LiftSensorSimulator(seed=7)
    r_norm = sim.generate_reading("LIFT-01", operating_mode="normal", inject_missing=False, inject_anomaly=False)
    for key in ("motor_temp", "vibration_level", "door_cycle_time", "motor_current", "cabin_load", "travel_time"):
        assert r_norm[key] is not None

    predictor = LiftBreakdownPredictor(
        model_path=trained_artifacts["model"],
        metrics_path=trained_artifacts["metrics"],
    )
    baseline = predictor.get_baseline_stats()

    drifted_rows = [
        {
            "motor_temp": 84.0,
            "vibration_level": 4.9,
            "door_cycle_time": 5.5,
            "motor_current": 36.0,
            "cabin_load": 520.0,
            "travel_time": 16.2,
        }
        for _ in range(15)
    ]
    drift = detect_sensor_drift(drifted_rows, baseline, min_samples=8)
    assert drift["status"] == "drift_detected"
    assert "motor_temp" in drift["drifting_sensors"]
    assert "limitations" in drift


def test_sqlite_persistence(isolated_env) -> None:
    db = isolated_env["db"]
    ts = datetime.now(timezone.utc).isoformat()
    rid = db.insert_sensor_reading(
        {
            "lift_id": "LIFT-01",
            "recorded_at": ts,
            "motor_temp": 54.0,
            "vibration_level": 1.2,
            "door_cycle_time": 2.9,
            "motor_current": 18.0,
            "cabin_load": 350.0,
            "travel_time": 10.2,
            "is_missing_any": False,
            "missing_fields": [],
            "quality_status": "ok",
            "quality_notes": "",
        }
    )
    assert rid > 0
    latest = db.get_latest_sensor_readings("LIFT-01")
    assert len(latest) == 1
    assert latest[0]["motor_temp"] == 54.0
