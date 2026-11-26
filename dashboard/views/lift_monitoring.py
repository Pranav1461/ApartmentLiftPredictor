"""Live Lift Monitoring page with horizontal threshold meters and 6-sensor telemetry grid."""

from __future__ import annotations

import html
from typing import Any

import pandas as pd
import streamlit as st

from dashboard.api_client import BackendClient
from dashboard.components.charts import (
    cabin_load_chart,
    door_cycle_chart,
    motor_current_chart,
    motor_temperature_chart,
    travel_time_chart,
    vibration_chart,
)
from dashboard.components.layout import (
    format_timestamp,
    render_html,
    render_section_label,
    render_sensor_meter,
    status_pill_html,
)
from ml.features import SENSOR_METADATA


def render(client: BackendClient, selected_lift: str, sys_status: dict[str, Any] | None) -> None:
    ok_lifts, lifts = client.list_lifts()
    if not ok_lifts or not lifts:
        st.error(f"Unable to load lifts: {lifts}")
        return

    lift_id = lifts[0]["lift_id"] if selected_lift == "All Lifts" else selected_lift
    ok_status, lift_status = client.get_lift_status(lift_id)
    ok_hist, history = client.get_sensor_history(lift_id=lift_id, limit=100)
    ok_qual, quality_summary = client.get_data_quality(lift_id=lift_id, limit=60)

    latest = (lift_status or {}).get("latest_reading") if ok_status else None
    drift = (lift_status or {}).get("drift") if ok_status else None
    lift_info = (lift_status or {}).get("lift") if ok_status else {}

    if not latest:
        st.info(f"No sensor readings recorded yet for {lift_id}. Ensure the simulator is running.")
        return

    render_section_label(
        f"Live Sensor Meters — {lift_id} ({lift_info.get('building_zone', '')} | Updated {format_timestamp(latest.get('recorded_at'))})"
    )

    m1, m2, m3 = st.columns(3, gap="medium")
    with m1:
        render_sensor_meter(
            "Motor Temperature",
            latest.get("motor_temp"),
            "°C",
            SENSOR_METADATA["motor_temp"]["warning_high"],
            SENSOR_METADATA["motor_temp"]["critical_high"],
            110.0,
            decimals=1,
        )
        render_sensor_meter(
            "Motor Current",
            latest.get("motor_current"),
            "A",
            SENSOR_METADATA["motor_current"]["warning_high"],
            SENSOR_METADATA["motor_current"]["critical_high"],
            55.0,
            decimals=1,
        )
    with m2:
        render_sensor_meter(
            "Vibration Level",
            latest.get("vibration_level"),
            "mm/s",
            SENSOR_METADATA["vibration_level"]["warning_high"],
            SENSOR_METADATA["vibration_level"]["critical_high"],
            8.0,
            decimals=2,
        )
        render_sensor_meter(
            "Cabin Load",
            latest.get("cabin_load"),
            "kg",
            SENSOR_METADATA["cabin_load"]["warning_high"],
            SENSOR_METADATA["cabin_load"]["critical_high"],
            1400.0,
            decimals=0,
        )
    with m3:
        render_sensor_meter(
            "Door Cycle Time",
            latest.get("door_cycle_time"),
            "s",
            SENSOR_METADATA["door_cycle_time"]["warning_high"],
            SENSOR_METADATA["door_cycle_time"]["critical_high"],
            8.0,
            decimals=2,
        )
        render_sensor_meter(
            "Travel Time",
            latest.get("travel_time"),
            "s",
            SENSOR_METADATA["travel_time"]["warning_high"],
            SENSOR_METADATA["travel_time"]["critical_high"],
            22.0,
            decimals=1,
        )

    q_col, d_col = st.columns(2, gap="medium")
    with q_col:
        render_section_label("Data Quality & Missing Sensor Check")
        q_stat = latest.get("quality_status", "ok")
        pill = status_pill_html(q_stat.upper(), "ok" if q_stat == "ok" else "warn")
        missing_count = (quality_summary or {}).get("missing_readings_count", 0) if ok_qual else 0
        out_range = (quality_summary or {}).get("out_of_range_count", 0) if ok_qual else 0
        render_html(
            f"""
            <div class="surface-box">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-weight:600;">Latest Reading Quality</span>{pill}
                </div>
                <div style="font-size:0.82rem; color:#94A3B8; margin-top:8px;">
                    Recent window (60 samples): <strong style="color:#FFFFFF;">{missing_count}</strong> readings with missing sensors,
                    <strong style="color:#FFFFFF;">{out_range}</strong> out-of-range events. Genuine 0.0 kg values remain distinct from missing NULLs.
                </div>
                <div style="font-size:0.8rem; color:#E2E8F0; margin-top:6px;">
                    {html.escape(latest.get("quality_notes") or "All 6 sensors reporting within physical bounds.")}
                </div>
            </div>
            """
        )

    with d_col:
        render_section_label("Sensor Drift Monitor")
        d_stat = (drift or {}).get("status", "unavailable")
        drifting = (drift or {}).get("drifting_sensors", [])
        d_pill = status_pill_html(
            "DRIFT DETECTED" if d_stat == "drift_detected" else d_stat.upper(),
            "warn" if d_stat == "drift_detected" else "ok",
        )
        drift_desc = (
            f"Drifting sensors relative to healthy baseline: {', '.join(drifting)}"
            if drifting
            else "Rolling sensor distribution aligns with healthy training baseline."
        )
        render_html(
            f"""
            <div class="surface-box">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-weight:600;">Rolling Baseline Check (n={(drift or {}).get('sample_count', 0)})</span>{d_pill}
                </div>
                <div style="font-size:0.82rem; color:#E2E8F0; margin-top:8px;">
                    {html.escape(drift_desc)}
                </div>
                <div style="font-size:0.75rem; color:#8491A3; margin-top:6px;">
                    Note: Rolling baseline comparison cannot separate calibration drift from sustained traffic or wear.
                </div>
            </div>
            """
        )

    hist_list = history if ok_hist else []
    c1, c2 = st.columns(2, gap="medium")
    with c1:
        st.plotly_chart(motor_temperature_chart(hist_list, height=265), width="stretch", theme=None, config={"displayModeBar": False})
    with c2:
        st.plotly_chart(vibration_chart(hist_list, height=265), width="stretch", theme=None, config={"displayModeBar": False})

    c3, c4 = st.columns(2, gap="medium")
    with c3:
        st.plotly_chart(door_cycle_chart(hist_list, height=265), width="stretch", theme=None, config={"displayModeBar": False})
    with c4:
        st.plotly_chart(motor_current_chart(hist_list, height=265), width="stretch", theme=None, config={"displayModeBar": False})

    c5, c6 = st.columns(2, gap="medium")
    with c5:
        st.plotly_chart(cabin_load_chart(hist_list, height=265), width="stretch", theme=None, config={"displayModeBar": False})
    with c6:
        st.plotly_chart(travel_time_chart(hist_list, height=265), width="stretch", theme=None, config={"displayModeBar": False})

    with st.expander("Recent Timestamped Sensor Log", expanded=False):
        if hist_list:
            df = pd.DataFrame(hist_list[:25])[
                [
                    "recorded_at",
                    "motor_temp",
                    "vibration_level",
                    "door_cycle_time",
                    "motor_current",
                    "cabin_load",
                    "travel_time",
                    "quality_status",
                    "quality_notes",
                ]
            ]
            st.dataframe(df, width="stretch", hide_index=True)
