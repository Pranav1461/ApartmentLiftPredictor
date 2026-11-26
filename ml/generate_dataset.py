"""Synthetic historical dataset generator for Apartment Lift breakdown prediction.

Simulates multi-lift telemetry across residential traffic cycles, transient rush-hour load
spikes, and gradual degradation episodes (traction bearing wear, door operator faults,
motor winding overload) with a 24-hour lookahead breakdown target (`breakdown_within_24h`).

Limitations:
- Simulated electromechanical degradation curves approximate real apartment traction lifts
  and cannot capture building-specific hoistway conditions, sudden power surges, or rare
  controller board faults absent in the simulation model.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from config import get_settings
from ml.features import SENSOR_FEATURES

TARGET_COLUMN = "breakdown_within_24h"


def generate_historical_dataset(
    output_path: str | Path | None = None,
    days: int = 90,
    interval_minutes: int = 15,
    lifts: tuple[str, ...] = ("LIFT-01", "LIFT-02", "LIFT-03"),
    seed: int = 42,
) -> pd.DataFrame:
    """Generate and save a labeled historical lift sensor dataset without target leakage."""
    rng = np.random.default_rng(seed)
    steps_per_day = int((24 * 60) / interval_minutes)
    total_steps = days * steps_per_day
    lookahead_steps = int((24 * 60) / interval_minutes)

    start_ts = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    records: list[dict[str, object]] = []

    fault_types = ("traction_bearing_wear", "door_operator_fault", "motor_winding_overload")

    for lift_idx, lift_id in enumerate(lifts):
        lift_temp_offset = rng.normal(0.0, 1.2)
        lift_vib_offset = rng.normal(0.0, 0.08)
        capacity_scale = 1.25 if lift_id == "LIFT-03" else 1.0

        # Schedule realistic breakdown events spaced across the timeline
        breakdown_events: list[tuple[int, int, str]] = []
        cursor = int(rng.integers(steps_per_day * 3, steps_per_day * 8))
        while cursor < total_steps - steps_per_day * 2:
            degrad_duration = int(rng.integers(int(18 * 60 / interval_minutes), int(44 * 60 / interval_minutes)))
            start_deg = max(0, cursor - degrad_duration)
            fault = fault_types[(len(breakdown_events) + lift_idx) % len(fault_types)]
            breakdown_events.append((start_deg, cursor, fault))
            cursor += int(rng.integers(steps_per_day * 7, steps_per_day * 15))

        # Transient heavy-traffic bursts that do NOT cause a breakdown
        traffic_bursts: list[tuple[int, int]] = []
        for _ in range(max(4, days // 10)):
            s = int(rng.integers(0, total_steps - 16))
            traffic_bursts.append((s, s + int(rng.integers(3, 12))))

        for step in range(total_steps):
            ts = start_ts + timedelta(minutes=step * interval_minutes)
            hour_of_day = ts.hour + ts.minute / 60.0
            # Morning (8:30) and evening (18:30) residential elevator rush cycles
            morning_peak = np.exp(-0.5 * ((hour_of_day - 8.5) / 2.2) ** 2)
            evening_peak = np.exp(-0.5 * ((hour_of_day - 18.5) / 2.5) ** 2)
            traffic = float(np.clip(0.2 + 0.75 * max(morning_peak, evening_peak), 0.15, 1.0))

            deg_progress = 0.0
            active_fault = None
            for start_deg, fail_step, fault in breakdown_events:
                if start_deg <= step <= fail_step:
                    deg_progress = (step - start_deg) / max(1, (fail_step - start_deg))
                    active_fault = fault
                    break

            burst_boost = 0.0
            for sp_start, sp_end in traffic_bursts:
                if sp_start <= step <= sp_end:
                    burst_boost = 1.0
                    break

            # Baseline healthy physics coupled to cabin load & traffic
            base_load = (160.0 + 420.0 * traffic + 240.0 * burst_boost) * capacity_scale
            base_load = float(np.clip(base_load + rng.normal(0.0, 55.0), 0.0, 1450.0 * capacity_scale))
            load_ratio = base_load / (1000.0 * capacity_scale)

            base_motor_temp = 46.5 + lift_temp_offset + 10.5 * traffic + 5.5 * load_ratio + 3.0 * burst_boost
            base_vib = 0.95 + lift_vib_offset + 0.55 * traffic + 0.35 * load_ratio + 0.25 * burst_boost
            base_door = 2.75 + 0.45 * traffic + 0.25 * burst_boost
            base_current = 14.0 + 10.5 * load_ratio + 3.0 * traffic + 2.5 * burst_boost
            base_travel = 9.2 + 1.6 * load_ratio + 0.7 * traffic + 0.6 * burst_boost

            # Gradual mechanical/electrical fault evolution
            if active_fault == "traction_bearing_wear":
                base_vib += 3.9 * (deg_progress ** 1.15)
                base_motor_temp += 22.0 * (deg_progress ** 1.25)
                base_current += 9.5 * (deg_progress ** 1.2)
                base_travel += 3.8 * (deg_progress ** 1.3)
                base_door += 0.4 * deg_progress
            elif active_fault == "door_operator_fault":
                base_door += 3.2 * (deg_progress ** 1.1)
                base_travel += 4.6 * (deg_progress ** 1.2)
                base_vib += 1.2 * deg_progress
                base_motor_temp += 10.0 * deg_progress
                base_current += 3.5 * deg_progress
            elif active_fault == "motor_winding_overload":
                base_current += 16.5 * (deg_progress ** 1.15)
                base_motor_temp += 29.0 * (deg_progress ** 1.2)
                base_travel += 5.0 * (deg_progress ** 1.3)
                base_vib += 1.9 * deg_progress

            motor_temp = float(np.clip(np.round(base_motor_temp + rng.normal(0.0, 1.5), 2), 20.0, 130.0))
            vibration_level = float(np.clip(np.round(base_vib + rng.normal(0.0, 0.16), 2), 0.1, 20.0))
            door_cycle_time = float(np.clip(np.round(base_door + rng.normal(0.0, 0.18), 2), 1.5, 18.0))
            motor_current = float(np.clip(np.round(base_current + rng.normal(0.0, 0.9), 2), 2.0, 70.0))
            cabin_load = float(np.round(base_load, 1))
            travel_time = float(np.clip(np.round(base_travel + rng.normal(0.0, 0.45), 2), 4.0, 45.0))

            breakdown_within_24h = 0
            for _, fail_step, _ in breakdown_events:
                if step < fail_step <= step + lookahead_steps or step == fail_step:
                    breakdown_within_24h = 1
                    break

            records.append(
                {
                    "timestamp": ts.isoformat(),
                    "lift_id": lift_id,
                    "motor_temp": motor_temp,
                    "vibration_level": vibration_level,
                    "door_cycle_time": door_cycle_time,
                    "motor_current": motor_current,
                    "cabin_load": cabin_load,
                    "travel_time": travel_time,
                    TARGET_COLUMN: breakdown_within_24h,
                }
            )

    df = pd.DataFrame.from_records(records)

    missing_rng = np.random.default_rng(seed + 99)
    for col in SENSOR_FEATURES:
        mask = missing_rng.random(len(df)) < 0.025
        df.loc[mask, col] = np.nan

    target_path = Path(output_path) if output_path else get_settings().resolved_path(
        get_settings().historical_dataset_path
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(target_path, index=False)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic historical lift sensor dataset.")
    parser.add_argument("--output", type=str, default=None, help="Output CSV path.")
    parser.add_argument("--days", type=int, default=90, help="Number of simulated days per lift.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    args = parser.parse_args()

    df = generate_historical_dataset(output_path=args.output, days=args.days, seed=args.seed)
    pos_rate = df[TARGET_COLUMN].mean() * 100.0
    print(f"Generated {len(df)} rows across {df['lift_id'].nunique()} lifts.")
    print(f"Positive class ({TARGET_COLUMN}=1) prevalence: {pos_rate:.2f}%")


if __name__ == "__main__":
    main()
