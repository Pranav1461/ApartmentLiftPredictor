"""Lift metadata, live operational status, and simulation mode endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from backend.dependencies import get_db, get_monitoring_service, require_operator_auth
from backend.schemas import LiftModeUpdate
from backend.services.monitoring_service import MonitoringService
from database.db import DatabaseManager

router = APIRouter(prefix="/api/v1/lifts", tags=["Lifts"])


@router.get("")
def list_lifts(db: DatabaseManager = Depends(get_db)) -> list[dict[str, Any]]:
    return db.list_lifts()


@router.get("/{lift_id}")
def get_lift(lift_id: str, db: DatabaseManager = Depends(get_db)) -> dict[str, Any]:
    lift = db.get_lift(lift_id)
    if not lift:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lift '{lift_id}' not found.")
    return lift


@router.get("/{lift_id}/status")
def get_lift_status(
    lift_id: str,
    db: DatabaseManager = Depends(get_db),
    mon_svc: MonitoringService = Depends(get_monitoring_service),
) -> dict[str, Any]:
    lift = db.get_lift(lift_id)
    if not lift:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lift '{lift_id}' not found.")
    latest_reading = db.get_latest_sensor_readings(lift_id=lift_id)
    latest_pred = db.get_latest_predictions(lift_id=lift_id)
    open_alert = db.get_open_alert_for_lift(lift_id)
    drift = mon_svc.get_lift_drift_report(lift_id=lift_id)
    return {
        "lift": lift,
        "latest_reading": latest_reading[0] if latest_reading else None,
        "latest_prediction": latest_pred[0] if latest_pred else None,
        "open_alert": open_alert,
        "drift": drift,
    }


@router.put("/{lift_id}/mode")
def set_lift_operating_mode(
    lift_id: str,
    payload: LiftModeUpdate,
    db: DatabaseManager = Depends(get_db),
    _actor: str = Depends(require_operator_auth),
) -> dict[str, Any]:
    updated = db.update_lift_status(lift_id, operating_mode=payload.operating_mode)
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lift '{lift_id}' not found.")
    return updated
