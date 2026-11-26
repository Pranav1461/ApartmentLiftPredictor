"""Monitoring pipeline service orchestrating ingestion, quality, prediction, and alerts."""

from __future__ import annotations

from typing import Any

from alerts.alert_service import AlertEngine
from backend.services.data_quality import detect_sensor_drift, evaluate_reading_quality
from backend.services.prediction_service import PredictionService
from database.db import DatabaseManager, utc_now_iso


class MonitoringService:
    """Processes incoming lift readings through validation, ML breakdown prediction, and alerting."""

    def __init__(
        self,
        db: DatabaseManager,
        prediction_service: PredictionService,
        alert_engine: AlertEngine,
    ) -> None:
        self.db = db
        self.prediction_service = prediction_service
        self.alert_engine = alert_engine

    def process_reading(self, raw_reading: dict[str, Any]) -> dict[str, Any]:
        """Validate, store, predict, and evaluate alert rules for one lift sensor reading."""
        lift_id = raw_reading["lift_id"]
        if not raw_reading.get("recorded_at"):
            raw_reading["recorded_at"] = utc_now_iso()

        sanitized = evaluate_reading_quality(raw_reading)

        if self.prediction_service.predictor.is_loaded():
            recent = self.db.get_sensor_history(lift_id=lift_id, limit=20)
            baseline = self.prediction_service.predictor.get_baseline_stats()
            drift_report = detect_sensor_drift([sanitized, *recent], baseline)
            if drift_report.get("status") == "drift_detected" and sanitized["quality_status"] == "ok":
                sanitized["quality_status"] = "drift_warning"
                drifting = ", ".join(drift_report["drifting_sensors"])
                sanitized["quality_notes"] = (
                    f"{sanitized['quality_notes']}; " if sanitized["quality_notes"] else ""
                ) + f"Baseline drift detected in: {drifting}"

        reading_id = self.db.insert_sensor_reading(sanitized)
        sanitized["id"] = reading_id

        prediction = self.prediction_service.predict_and_store(sanitized, reading_id=reading_id)
        alert = self.alert_engine.evaluate_prediction(
            lift_id=lift_id,
            prediction_id=prediction["id"],
            prediction=prediction,
            reading=sanitized,
        )

        return {
            "reading": sanitized,
            "prediction": prediction,
            "alert": alert,
        }

    def get_lift_drift_report(self, lift_id: str, window_size: int = 20) -> dict[str, Any]:
        recent = self.db.get_sensor_history(lift_id=lift_id, limit=window_size)
        baseline = (
            self.prediction_service.predictor.get_baseline_stats()
            if self.prediction_service.predictor.is_loaded()
            else {}
        )
        report = detect_sensor_drift(recent, baseline)
        report["lift_id"] = lift_id
        return report
