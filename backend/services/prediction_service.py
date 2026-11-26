"""Prediction service coordinating model inference and SQLite persistence."""

from __future__ import annotations

from typing import Any

from database.db import DatabaseManager
from ml.predict import LiftBreakdownPredictor


class PredictionService:
    """Wraps LiftBreakdownPredictor and records inference outputs into SQLite."""

    def __init__(self, db: DatabaseManager, predictor: LiftBreakdownPredictor | None = None) -> None:
        self.db = db
        self.predictor = predictor or LiftBreakdownPredictor()

    def ensure_ready(self) -> None:
        self.predictor.ensure_loaded()

    def get_alert_threshold(self) -> float:
        settings = self.db.get_system_settings()
        return float(settings.get("alert_threshold", "0.70"))

    def predict_and_store(self, reading: dict[str, Any], reading_id: int | None = None) -> dict[str, Any]:
        threshold = self.get_alert_threshold()
        result = self.predictor.predict_reading(reading, alert_threshold=threshold)
        result["reading_id"] = reading_id
        pred_id = self.db.insert_prediction(result)
        result["id"] = pred_id
        return result
