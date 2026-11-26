"""Breakdown Prediction page featuring bullet risk meter and diverging Z-score deviations."""

from __future__ import annotations

import html
from typing import Any

import pandas as pd
import streamlit as st

from dashboard.api_client import BackendClient
from dashboard.components.charts import (
    breakdown_bullet_chart,
    breakdown_probability_trend_chart,
    contributing_factors_diverging_chart,
)
from dashboard.components.layout import format_timestamp, render_html, render_section_label, status_pill_html


def render(client: BackendClient, selected_lift: str, sys_status: dict[str, Any] | None) -> None:
    ok_lifts, lifts = client.list_lifts()
    if not ok_lifts or not lifts:
        st.error(f"Unable to load lifts: {lifts}")
        return

    lift_id = lifts[0]["lift_id"] if selected_lift == "All Lifts" else selected_lift
    settings = (sys_status or {}).get("settings", {})
    threshold = float(settings.get("alert_threshold", "0.70"))

    ok_latest_p, latest_preds = client.get_latest_predictions(lift_id=lift_id)
    ok_hist_p, pred_history = client.get_prediction_history(
        lift_id=None if selected_lift == "All Lifts" else lift_id,
        limit=150,
    )

    latest = latest_preds[0] if (ok_latest_p and latest_preds) else None
    if not latest:
        st.info(f"No breakdown predictions generated yet for {lift_id}.")
        return

    prob = float(latest["breakdown_probability"])
    risk_level = latest["risk_level"]
    pred_status = "Breakdown Predicted (<=24h)" if latest["predicted_class"] == 1 else "Normal Operation"
    factors = latest.get("contributing_factors", [])

    col_left, col_right = st.columns([1.05, 1.35], gap="medium")
    with col_left:
        render_section_label(f"24-Hour Breakdown Risk — {lift_id}")
        st.plotly_chart(
            breakdown_bullet_chart(prob, threshold=threshold, lift_id=lift_id),
            width="stretch",
            theme=None,
            config={"displayModeBar": False},
        )
        render_html(
            f"""
            <div class="surface-box">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-weight:700; font-size:0.95rem;">{html.escape(pred_status)} ({prob * 100:.2f}%)</span>
                    {status_pill_html(risk_level + " RISK", risk_level)}
                </div>
                <div style="font-size:0.78rem; color:#CBD5E1; margin-top:8px;">
                    Evaluated: {html.escape(format_timestamp(latest.get('predicted_at')))}<br>
                    Model: {html.escape(latest.get('model_version', 'rf-lift-predictor-v1.0'))} |
                    Alert Threshold: {threshold * 100:.0f}%
                </div>
                <div style="font-size:0.74rem; color:#8491A3; margin-top:8px;">
                    Risk Tiers: Low (&lt;40%) | Medium (40-69%) | High (70-89%) | Critical (&ge;90%)
                </div>
            </div>
            """
        )

    with col_right:
        render_section_label("Main Contributing Sensor Factors")
        if factors:
            st.plotly_chart(
                contributing_factors_diverging_chart(factors),
                width="stretch",
                theme=None,
                config={"displayModeBar": False},
            )

    if factors:
        df_factors = pd.DataFrame(factors)[
            ["label", "value", "unit", "baseline_mean", "z_score", "direction", "model_importance"]
        ]
        df_factors.columns = [
            "Sensor Metric",
            "Current Value",
            "Unit",
            "Healthy Baseline",
            "Z-Score",
            "State",
            "Model Weight",
        ]
        df_factors["Model Weight"] = (df_factors["Model Weight"] * 100).round(2).astype(str) + "%"
        st.dataframe(df_factors, width="stretch", hide_index=True)

    render_section_label("Prediction History & Timeline")
    hist_rows = pred_history if ok_hist_p else []
    st.plotly_chart(
        breakdown_probability_trend_chart(hist_rows, threshold=threshold, height=280),
        width="stretch",
        theme=None,
        config={"displayModeBar": False},
    )

    if hist_rows:
        df_hist = pd.DataFrame(hist_rows[:50])[
            ["predicted_at", "lift_id", "breakdown_probability", "risk_level", "predicted_class", "model_version"]
        ]
        df_hist["breakdown_probability"] = (df_hist["breakdown_probability"] * 100).round(2).astype(str) + "%"
        df_hist["predicted_class"] = df_hist["predicted_class"].map({0: "Normal (0)", 1: "Breakdown <=24h (1)"})
        df_hist.columns = ["Timestamp", "Lift", "Probability", "Risk Level", "Predicted Class", "Model"]
        st.dataframe(df_hist, width="stretch", hide_index=True, height=250)
