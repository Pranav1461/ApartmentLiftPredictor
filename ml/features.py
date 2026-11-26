"""Shared lift sensor schema, physical bounds, and risk classification rules."""

from __future__ import annotations

from typing import Any

SENSOR_FEATURES: list[str] = [
    "motor_temp",
    "vibration_level",
    "door_cycle_time",
    "motor_current",
    "cabin_load",
    "travel_time",
]

SENSOR_METADATA: dict[str, dict[str, Any]] = {
    "motor_temp": {
        "label": "Motor Temperature",
        "unit": "°C",
        "normal_min": 40.0,
        "normal_max": 68.0,
        "warning_high": 75.0,
        "critical_high": 85.0,
        "physical_min": 0.0,
        "physical_max": 140.0,
    },
    "vibration_level": {
        "label": "Vibration Level",
        "unit": "mm/s",
        "normal_min": 0.3,
        "normal_max": 2.5,
        "warning_high": 3.5,
        "critical_high": 5.0,
        "physical_min": 0.0,
        "physical_max": 25.0,
    },
    "door_cycle_time": {
        "label": "Door Cycle Time",
        "unit": "s",
        "normal_min": 2.2,
        "normal_max": 3.9,
        "warning_high": 4.6,
        "critical_high": 5.8,
        "physical_min": 0.5,
        "physical_max": 25.0,
    },
    "motor_current": {
        "label": "Motor Current",
        "unit": "A",
        "normal_min": 10.0,
        "normal_max": 28.0,
        "warning_high": 33.0,
        "critical_high": 39.0,
        "physical_min": 0.0,
        "physical_max": 80.0,
    },
    "cabin_load": {
        "label": "Cabin Load",
        "unit": "kg",
        "normal_min": 0.0,
        "normal_max": 850.0,
        "warning_high": 920.0,
        "critical_high": 1020.0,
        "physical_min": 0.0,
        "physical_max": 2200.0,
    },
    "travel_time": {
        "label": "Travel Time",
        "unit": "s",
        "normal_min": 7.5,
        "normal_max": 12.8,
        "warning_high": 14.5,
        "critical_high": 17.0,
        "physical_min": 1.0,
        "physical_max": 60.0,
    },
}


def classify_risk_level(breakdown_probability: float) -> str:
    """Classify breakdown probability into Low, Medium, High, or Critical."""
    if breakdown_probability >= 0.90:
        return "Critical"
    if breakdown_probability >= 0.70:
        return "High"
    if breakdown_probability >= 0.40:
        return "Medium"
    return "Low"
