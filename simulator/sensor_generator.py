"""Continuous multi-lift apartment elevator sensor simulator."""

from __future__ import annotations

import argparse
import logging
import math
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import requests

from config import get_settings
from database.db import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass
class LiftSimulationState:
    lift_id: str
    step: int = 0
    degradation_level: float = 0.0
    fault_profile: str = "traction_bearing_wear"
    rng: np.random.Generator = field(default_factory=lambda: np.random.default_rng(100))


class LiftSensorSimulator:
    """Generates physically correlated lift sensor readings across normal, warning, and critical states."""

    def __init__(self, seed: int = 2026) -> None:
        self.base_seed = seed
        self.lift_states: dict[str, LiftSimulationState] = {
            "LIFT-01": LiftSimulationState(
                lift_id="LIFT-01",
                fault_profile="traction_bearing_wear",
                rng=np.random.default_rng(seed + 1),
            ),
            "LIFT-02": LiftSimulationState(
                lift_id="LIFT-02",
                fault_profile="door_operator_fault",
                rng=np.random.default_rng(seed + 2),
            ),
            "LIFT-03": LiftSimulationState(
                lift_id="LIFT-03",
                fault_profile="motor_winding_overload",
                rng=np.random.default_rng(seed + 3),
            ),
        }

    def get_lift_state(self, lift_id: str) -> LiftSimulationState:
        if lift_id not in self.lift_states:
            self.lift_states[lift_id] = LiftSimulationState(
                lift_id=lift_id,
                rng=np.random.default_rng(self.base_seed + len(self.lift_states) + 10),
            )
        return self.lift_states[lift_id]

    def generate_reading(
        self,
        lift_id: str,
        operating_mode: str = "normal",
        inject_missing: bool = True,
        inject_anomaly: bool = True,
    ) -> dict[str, Any]:
        """Generate one physically correlated reading for a lift given its operating mode."""
        state = self.get_lift_state(lift_id)
        state.step += 1
        rng = state.rng

        if operating_mode == "critical":
            state.degradation_level = min(1.0, max(0.85, state.degradation_level + 0.08))
        elif operating_mode == "degrading":
            state.degradation_level = min(0.95, max(0.45, state.degradation_level + 0.05))
        else:
            if state.degradation_level > 0.0:
                state.degradation_level = max(0.0, state.degradation_level - 0.12)

        now = datetime.now(timezone.utc)
        hour = now.hour + now.minute / 60.0 + now.second / 3600.0
        morning_peak = math.exp(-0.5 * ((hour - 8.5) / 2.2) ** 2)
        evening_peak = math.exp(-0.5 * ((hour - 18.5) / 2.5) ** 2)
        traffic = min(max(0.2 + 0.75 * max(morning_peak, evening_peak), 0.15), 1.0)

        capacity_scale = 1.25 if lift_id == "LIFT-03" else 1.0
        deg = state.degradation_level

        base_load = (170.0 + 400.0 * traffic) * capacity_scale
        base_load = float(np.clip(base_load + rng.normal(0.0, 50.0), 0.0, 1450.0 * capacity_scale))
        load_ratio = base_load / (1000.0 * capacity_scale)

        base_motor_temp = 47.0 + 10.0 * traffic + 5.5 * load_ratio
        base_vib = 0.95 + 0.50 * traffic + 0.35 * load_ratio
        base_door = 2.75 + 0.42 * traffic
        base_current = 14.0 + 10.2 * load_ratio + 2.8 * traffic
        base_travel = 9.2 + 1.5 * load_ratio + 0.65 * traffic

        if deg > 0.0:
            if state.fault_profile == "traction_bearing_wear":
                base_vib += 4.1 * (deg ** 1.1)
                base_motor_temp += 23.0 * (deg ** 1.2)
                base_current += 10.0 * (deg ** 1.15)
                base_travel += 4.0 * (deg ** 1.25)
                base_door += 0.45 * deg
            elif state.fault_profile == "door_operator_fault":
                base_door += 3.3 * (deg ** 1.05)
                base_travel += 4.8 * (deg ** 1.15)
                base_vib += 1.3 * deg
                base_motor_temp += 11.0 * deg
                base_current += 3.8 * deg
            else:  # motor_winding_overload
                base_current += 17.0 * (deg ** 1.1)
                base_motor_temp += 30.0 * (deg ** 1.15)
                base_travel += 5.2 * (deg ** 1.25)
                base_vib += 2.0 * deg

        motor_temp: float | None = float(np.clip(np.round(base_motor_temp + rng.normal(0.0, 1.3), 2), 20.0, 130.0))
        vibration_level: float | None = float(np.clip(np.round(base_vib + rng.normal(0.0, 0.14), 2), 0.1, 20.0))
        door_cycle_time: float | None = float(np.clip(np.round(base_door + rng.normal(0.0, 0.15), 2), 1.5, 18.0))
        motor_current: float | None = float(np.clip(np.round(base_current + rng.normal(0.0, 0.8), 2), 1.0, 70.0))
        cabin_load: float | None = float(np.round(base_load, 1))
        travel_time: float | None = float(np.clip(np.round(base_travel + rng.normal(0.0, 0.4), 2), 4.0, 45.0))

        # Occasional minor transient load/vibration spike during healthy operation
        if inject_anomaly and operating_mode == "normal" and rng.random() < 0.015:
            vibration_level = float(np.round(vibration_level + float(rng.uniform(0.8, 1.4)), 2))

        # Occasional missing reading (~2.5% chance on at most one sensor)
        if inject_missing and rng.random() < 0.025:
            choice = str(
                rng.choice(
                    [
                        "motor_temp",
                        "vibration_level",
                        "door_cycle_time",
                        "motor_current",
                        "cabin_load",
                        "travel_time",
                    ]
                )
            )
            if choice == "motor_temp":
                motor_temp = None
            elif choice == "vibration_level":
                vibration_level = None
            elif choice == "door_cycle_time":
                door_cycle_time = None
            elif choice == "motor_current":
                motor_current = None
            elif choice == "cabin_load":
                cabin_load = None
            elif choice == "travel_time":
                travel_time = None

        return {
            "lift_id": lift_id,
            "recorded_at": now.isoformat(timespec="milliseconds"),
            "motor_temp": motor_temp,
            "vibration_level": vibration_level,
            "door_cycle_time": door_cycle_time,
            "motor_current": motor_current,
            "cabin_load": cabin_load,
            "travel_time": travel_time,
        }


def run_api_simulator_loop(api_base_url: str | None = None) -> None:
    """Continuously poll backend settings and push generated lift readings via FastAPI."""
    settings = get_settings()
    base_url = (api_base_url or settings.api_base_url).rstrip("/")
    simulator = LiftSensorSimulator()

    logger.info("Starting continuous lift sensor simulator targeting %s", base_url)
    while True:
        interval = settings.simulator_interval_seconds
        enabled = True
        lifts: list[dict[str, Any]] = []

        try:
            status_resp = requests.get(f"{base_url}/api/v1/system/status", timeout=5)
            if status_resp.ok:
                sys_data = status_resp.json()
                sys_settings = sys_data.get("settings", {})
                enabled = str(sys_settings.get("simulator_enabled", "true")).lower() == "true"
                interval = max(1, int(float(sys_settings.get("simulator_interval_seconds", interval))))

            lifts_resp = requests.get(f"{base_url}/api/v1/lifts", timeout=5)
            if lifts_resp.ok:
                lifts = lifts_resp.json()
        except Exception as exc:
            logger.warning("Simulator unable to reach backend (%s); retrying in %ss", exc, interval)
            time.sleep(interval)
            continue

        if enabled and lifts:
            for lift in lifts:
                reading = simulator.generate_reading(
                    lift_id=lift["lift_id"],
                    operating_mode=lift.get("operating_mode", "normal"),
                )
                try:
                    resp = requests.post(f"{base_url}/api/v1/sensors/ingest", json=reading, timeout=5)
                    if not resp.ok:
                        logger.warning("Ingest failed for %s: %s", lift["lift_id"], resp.text)
                except Exception as exc:
                    logger.warning("Failed posting reading for %s: %s", lift["lift_id"], exc)

        time.sleep(interval)


def run_direct_db_tick(db: DatabaseManager, simulator: LiftSensorSimulator) -> list[dict[str, Any]]:
    """Utility for generating one tick across all DB lifts without HTTP."""
    lifts = db.list_lifts()
    return [
        simulator.generate_reading(
            lift_id=lift["lift_id"],
            operating_mode=lift.get("operating_mode", "normal"),
        )
        for lift in lifts
    ]


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Run Apartment Lift sensor simulator.")
    parser.add_argument("--api-url", type=str, default=None, help="FastAPI base URL.")
    args = parser.parse_args()
    run_api_simulator_loop(api_base_url=args.api_url)
