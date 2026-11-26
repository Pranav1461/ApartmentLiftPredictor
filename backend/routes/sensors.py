"""Sensor ingestion, history, quality, and drift endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from backend.dependencies import get_db, get_monitoring_service, require_operator_auth
from backend.schemas import SensorReadingIn
from backend.services.monitoring_service import MonitoringService
from database.db import DatabaseManager

router = APIRouter(prefix="/api/v1/sensors", tags=["Sensors"])


@router.get("/latest")
def get_latest_sensors(
    lift_id: str | None = Query(default=None),
    db: DatabaseManager = Depends(get_db),
) -> list[dict[str, Any]]:
    return db.get_latest_sensor_readings(lift_id=lift_id)


@router.get("/history")
def get_sensor_history(
    lift_id: str | None = Query(default=None),
    start_time: str | None = Query(default=None),
    end_time: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=2000),
    db: DatabaseManager = Depends(get_db),
) -> list[dict[str, Any]]:
    return db.get_sensor_history(
        lift_id=lift_id,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )


@router.post("/ingest", status_code=status.HTTP_201_CREATED)
def ingest_sensor_reading(
    payload: SensorReadingIn,
    db: DatabaseManager = Depends(get_db),
    mon_svc: MonitoringService = Depends(get_monitoring_service),
) -> dict[str, Any]:
    if not db.get_lift(payload.lift_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown lift '{payload.lift_id}'.",
        )
    return mon_svc.process_reading(payload.model_dump())


@router.post("/simulate-tick")
def trigger_simulation_tick(
    request: Request,
    db: DatabaseManager = Depends(get_db),
    mon_svc: MonitoringService = Depends(get_monitoring_service),
    _actor: str = Depends(require_operator_auth),
) -> dict[str, Any]:
    simulator = request.app.state.simulator
    lifts = db.list_lifts()
    results: list[dict[str, Any]] = []
    for lift in lifts:
        reading = simulator.generate_reading(
            lift_id=lift["lift_id"],
            operating_mode=lift.get("operating_mode", "normal"),
        )
        results.append(mon_svc.process_reading(reading))
    return {"processed": len(results), "results": results}


@router.get("/drift")
def get_sensor_drift(
    lift_id: str | None = Query(default=None),
    window: int = Query(default=20, ge=5, le=200),
    db: DatabaseManager = Depends(get_db),
    mon_svc: MonitoringService = Depends(get_monitoring_service),
) -> dict[str, Any]:
    if lift_id:
        if not db.get_lift(lift_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lift '{lift_id}' not found.")
        return mon_svc.get_lift_drift_report(lift_id=lift_id, window_size=window)

    lifts = db.list_lifts()
    return {
        "lifts": [mon_svc.get_lift_drift_report(lift_id=l["lift_id"], window_size=window) for l in lifts]
    }


@router.get("/quality")
def get_data_quality_summary(
    lift_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=10, le=1000),
    db: DatabaseManager = Depends(get_db),
) -> dict[str, Any]:
    readings = db.get_sensor_history(lift_id=lift_id, limit=limit)
    total = len(readings)
    missing_rows = sum(1 for r in readings if r.get("is_missing_any"))
    out_of_range_rows = sum(1 for r in readings if r.get("quality_status") == "out_of_range")
    drift_rows = sum(1 for r in readings if r.get("quality_status") == "drift_warning")
    recent_warnings = [r for r in readings if r.get("quality_status") != "ok"][:20]
    return {
        "sample_size": total,
        "missing_readings_count": missing_rows,
        "out_of_range_count": out_of_range_rows,
        "drift_warning_count": drift_rows,
        "recent_warnings": recent_warnings,
    }
