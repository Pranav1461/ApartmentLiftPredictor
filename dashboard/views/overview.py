"""Overview page with architectural split telemetry, bullet risk meter, and timeline alerts."""

from __future__ import annotations

import html
from typing import Any

import pandas as pd
import streamlit as st

from dashboard.api_client import BackendClient
from dashboard.components.charts import (
    breakdown_bullet_chart,
    breakdown_probability_trend_chart,
    lift_operating_performance_chart,
    motor_temperature_chart,
)
from dashboard.components.layout import (
    format_timestamp,
    render_html,
    render_metric_bar,
    render_section_label,
    status_pill_html,
)


def render(client: BackendClient, selected_lift: str, sys_status: dict[str, Any] | None) -> None:
    ok_lifts, lifts = client.list_lifts()
    ok_latest_s, latest_sensors = client.get_latest_sensors()
    ok_latest_p, latest_preds = client.get_latest_predictions()
    lift_param = None if selected_lift == "All Lifts" else selected_lift
    ok_hist, sensor_history = client.get_sensor_history(lift_id=lift_param, limit=120)
    ok_pred_hist, pred_history = client.get_prediction_history(lift_id=lift_param, limit=120)
    ok_alerts, alerts = client.list_alerts(limit=10)

    if not ok_lifts:
        st.error(f"Unable to load lift telemetry from backend: {lifts}")
        return

    lifts_list = lifts or []
    latest_s_map = {r["lift_id"]: r for r in (latest_sensors or [])} if ok_latest_s else {}
    latest_p_map = {p["lift_id"]: p for p in (latest_preds or [])} if ok_latest_p else {}

    summary = (sys_status or {}).get("summary", {})
    settings = (sys_status or {}).get("settings", {})
    threshold = float(settings.get("alert_threshold", "0.70"))

    total_lifts = int(summary.get("total_lifts", len(lifts_list)))
    operational_lifts = int(summary.get("operational_lifts", 0))
    attention_lifts = int(summary.get("attention_lifts", 0))
    active_alerts = int(summary.get("active_alerts", 0))

    focus_lift = lifts_list[0]["lift_id"] if (selected_lift == "All Lifts" and lifts_list) else selected_lift
    focus_reading = latest_s_map.get(focus_lift, {})
    focus_pred = latest_p_map.get(focus_lift, {})

    highest_prob = max((p.get("breakdown_probability", 0.0) for p in latest_p_map.values()), default=0.0)
    motor_temp_val = focus_reading.get("motor_temp")
    vib_val = focus_reading.get("vibration_level")
    overall_status = "ATTENTION" if attention_lifts > 0 or active_alerts > 0 else "NOMINAL"

    # Row 1: Split 4-column executive metric strip
    render_metric_bar(
        [
            {
                "label": "Fleet Availability",
                "value": f"{operational_lifts} / {total_lifts}",
                "sub": f"{attention_lifts} requiring attention | Status: {overall_status}",
                "tone": "warn" if attention_lifts > 0 else "ok",
            },
            {
                "label": "Active Breakdown Alerts",
                "value": str(active_alerts),
                "sub": "Independent background monitor",
                "tone": "crit" if active_alerts > 0 else "ok",
            },
            {
                "label": "Highest 24h Risk",
                "value": f"{highest_prob * 100:.1f}%",
                "sub": f"Alert trigger >= {threshold * 100:.0f}%",
                "tone": "crit" if highest_prob >= 0.90 else ("warn" if highest_prob >= threshold else "ok"),
            },
            {
                "label": f"Motor Temp ({focus_lift})",
                "value": f"{motor_temp_val:.1f} °C" if motor_temp_val is not None else "--",
                "sub": f"Vibration: {vib_val:.2f} mm/s" if vib_val is not None else "Vibration: --",
                "tone": "crit" if (motor_temp_val is not None and motor_temp_val >= 85.0) else (
                    "warn" if (motor_temp_val is not None and motor_temp_val >= 75.0) else "ok"
                ),
            },
        ]
    )

    # Row 2: Motor Temperature Profile + Operating Performance (Bar + Door Cycle)
    col_temp, col_perf = st.columns([1.15, 1.0], gap="medium")
    with col_temp:
        st.plotly_chart(
            motor_temperature_chart(sensor_history if ok_hist else [], height=305),
            width="stretch",
            theme=None,
            config={"displayModeBar": False},
        )
    with col_perf:
        perf_history = [r for r in (sensor_history if ok_hist else []) if r.get("lift_id") == focus_lift]
        st.plotly_chart(
            lift_operating_performance_chart(perf_history, height=305),
            width="stretch",
            theme=None,
            config={"displayModeBar": False},
        )

    # Row 3: Bullet Risk Meter + Shaft Health Progress Strips + Timeline Alert Feed
    col_bullet, col_shafts, col_feed = st.columns([0.95, 1.05, 1.05], gap="medium")

    with col_bullet:
        render_section_label(f"24h Breakdown Risk ({focus_lift})")
        prob_val = float(focus_pred.get("breakdown_probability", 0.0)) if focus_pred else 0.0
        st.plotly_chart(
            breakdown_bullet_chart(prob_val, threshold=threshold, lift_id=focus_lift),
            width="stretch",
            theme=None,
            config={"displayModeBar": False},
        )
        if focus_pred:
            risk_lvl = focus_pred.get("risk_level", "Low")
            pred_status = "Breakdown Predicted (<=24h)" if focus_pred.get("predicted_class") == 1 else "Normal Operation"
            render_html(
                f"""
                <div class="surface-box" style="padding:10px 12px;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="font-size:0.82rem; font-weight:600;">{html.escape(pred_status)}</span>
                        {status_pill_html(risk_lvl + " RISK", risk_lvl)}
                    </div>
                    <div style="font-size:0.74rem; color:#8491A3; margin-top:4px;">
                        Evaluated: {html.escape(format_timestamp(focus_pred.get('predicted_at')))}
                    </div>
                </div>
                """
            )

    with col_shafts:
        render_section_label("Lift Shaft Status Strips")
        for lft in lifts_list:
            lid = lft["lift_id"]
            r = latest_s_map.get(lid, {})
            p = latest_p_map.get(lid, {})
            prob_pct = float(p.get("breakdown_probability", 0.0)) * 100.0 if p else 0.0
            bar_col = "#EF4444" if prob_pct >= 90 else ("#F59E0B" if prob_pct >= threshold * 100 else "#2563EB")
            l_temp = f"{r['motor_temp']:.1f}°C" if r.get("motor_temp") is not None else "Missing"
            l_load = f"{r['cabin_load']:.0f} kg" if r.get("cabin_load") is not None else "Missing"
            pill = status_pill_html(lft["status"], lft["status"])
            render_html(
                f"""
                <div class="shaft-row">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <strong style="font-size:0.86rem; color:#FFFFFF;">{html.escape(lid)} &middot; {html.escape(lft['name'])}</strong>
                        {pill}
                    </div>
                    <div style="font-size:0.75rem; color:#94A3B8; margin-top:3px;">
                        Motor: {l_temp} | Load: {l_load} | Risk: <strong style="color:#FFFFFF;">{prob_pct:.1f}%</strong>
                    </div>
                    <div class="progress-track">
                        <div class="progress-fill" style="width:{max(prob_pct, 2.0):.1f}%; background-color:{bar_col};"></div>
                    </div>
                </div>
                """
            )

    with col_feed:
        render_section_label("Recent Breakdown-Risk Events")
        alert_items = alerts if ok_alerts and alerts else []
        if not alert_items:
            st.info("No alerts recorded yet. Background monitor active.")
        else:
            for al in alert_items[:3]:
                sev = al.get("severity", "warning")
                cls = "timeline-item timeline-crit" if sev == "critical" else "timeline-item"
                render_html(
                    f"""
                    <div class="{cls}">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <strong style="font-size:0.83rem;">{html.escape(al['title'])}</strong>
                            {status_pill_html(al['status'], al['status'])}
                        </div>
                        <div style="font-size:0.73rem; color:#8491A3; margin-top:4px;">
                            {html.escape(format_timestamp(al['created_at']))} | Email: {html.escape(al.get('email_delivery_status', 'n/a'))}
                        </div>
                    </div>
                    """
                )

    # Row 4: Historical Risk Timeline + Recent Sensor Telemetry Table
    col_hist_p, col_recent_s = st.columns([1.0, 1.15], gap="medium")
    with col_hist_p:
        render_section_label("Historical Breakdown Risk")
        st.plotly_chart(
            breakdown_probability_trend_chart(pred_history if ok_pred_hist else [], threshold=threshold, height=265),
            width="stretch",
            theme=None,
            config={"displayModeBar": False},
        )
    with col_recent_s:
        render_section_label("Recent Sensor Readings")
        rows = (sensor_history if ok_hist else [])[:8]
        if rows:
            df_show = pd.DataFrame(rows)[
                [
                    "recorded_at",
                    "lift_id",
                    "motor_temp",
                    "vibration_level",
                    "door_cycle_time",
                    "motor_current",
                    "cabin_load",
                    "travel_time",
                    "quality_status",
                ]
            ]
            df_show.columns = [
                "Timestamp",
                "Lift",
                "Motor °C",
                "Vib mm/s",
                "Door s",
                "Current A",
                "Load kg",
                "Travel s",
                "Quality",
            ]
            st.dataframe(df_show, width="stretch", hide_index=True, height=255)
        else:
            st.info("Waiting for sensor readings...")
