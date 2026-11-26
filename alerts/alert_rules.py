"""Alert rules, risk mapping, inspection recommendations, and cooldown helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ml.features import SENSOR_METADATA, classify_risk_level


def severity_from_probability(probability: float) -> str:
    """Map breakdown probability to alert severity ('critical' or 'warning')."""
    if probability >= 0.90:
        return "critical"
    return "warning"


def build_recommended_action(readings: dict[str, Any], contributing_factors: list[dict[str, Any]]) -> str:
    """Generate a specific elevator technician inspection recommendation from anomalies."""
    actions: list[str] = []

    motor_temp = readings.get("motor_temp")
    vib = readings.get("vibration_level")
    door = readings.get("door_cycle_time")
    current = readings.get("motor_current")
    load = readings.get("cabin_load")
    travel = readings.get("travel_time")

    if motor_temp is not None and float(motor_temp) >= SENSOR_METADATA["motor_temp"]["warning_high"]:
        actions.append(
            "Elevated motor temperature: inspect machine room ventilation, motor cooling fan, and brake drag."
        )
    if vib is not None and float(vib) >= SENSOR_METADATA["vibration_level"]["warning_high"]:
        actions.append(
            "Excessive mechanical vibration: inspect traction sheave bearings, rope tension balance, and guide shoes."
        )
    if door is not None and float(door) >= SENSOR_METADATA["door_cycle_time"]["warning_high"]:
        actions.append(
            "Sluggish door cycle time: inspect door operator drive belt, sill tracks, and interlock contacts."
        )
    if current is not None and float(current) >= SENSOR_METADATA["motor_current"]["warning_high"]:
        actions.append(
            "Abnormal motor current draw: inspect VFD inverter stage, motor windings, and counterweight balance."
        )
    if travel is not None and float(travel) >= SENSOR_METADATA["travel_time"]["warning_high"]:
        actions.append(
            "Extended floor-to-floor travel time: verify speed encoder feedback and leveling sensors."
        )
    if load is not None and float(load) >= SENSOR_METADATA["cabin_load"]["warning_high"]:
        actions.append(
            "Heavy cabin load condition: verify load-weighing cell calibration and overload bypass."
        )

    if not actions and contributing_factors:
        top = contributing_factors[0]
        actions.append(
            f"Inspect {top.get('label', 'lift subsystem')} (reading={top.get('value')} {top.get('unit', '')}) "
            "and perform preventive mechanical check."
        )
    if not actions:
        actions.append("Dispatch elevator technician to inspect traction motor, door operator, and controller logs.")

    return " ".join(actions)


def is_within_cooldown(last_notified_at: str | None, cooldown_minutes: int, now: datetime | None = None) -> bool:
    """Return True if last notification timestamp falls inside the cooldown window."""
    if not last_notified_at:
        return False
    current_time = now or datetime.now(timezone.utc)
    try:
        prev_time = datetime.fromisoformat(last_notified_at)
        if prev_time.tzinfo is None:
            prev_time = prev_time.replace(tzinfo=timezone.utc)
    except ValueError:
        return False
    return (current_time - prev_time) < timedelta(minutes=cooldown_minutes)


def evaluate_alert_trigger(probability: float, threshold: float = 0.70) -> tuple[bool, str, str]:
    """Return (should_trigger, risk_level, severity)."""
    risk_level = classify_risk_level(probability)
    severity = severity_from_probability(probability)
    return (probability >= threshold, risk_level, severity)
