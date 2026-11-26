"""Pure-black OLED Plotly charts for Apartment Lift Breakdown Predictor."""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go

from ml.features import SENSOR_METADATA

PLOT_BG = "#0B0E14"
PAPER_BG = "#0B0E14"
GRID_COLOR = "#1A202C"
TEXT_COLOR = "#F8FAFC"
MUTED_COLOR = "#8491A3"
COBALT = "#2563EB"
SKY = "#38BDF8"
TEAL = "#14B8A6"
EMERALD = "#22C55E"
AMBER = "#F59E0B"
CRIMSON = "#EF4444"

LIFT_COLORS = {
    "LIFT-01": "#2563EB",
    "LIFT-02": "#14B8A6",
    "LIFT-03": "#F59E0B",
}


def _apply_black_layout(
    fig: go.Figure,
    title: str,
    y_title: str,
    height: int = 300,
    x_title: str = "",
) -> go.Figure:
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color="#FFFFFF"), x=0.01, xanchor="left", y=0.96),
        height=height,
        margin=dict(l=54, r=18, t=64, b=38),
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PLOT_BG,
        font=dict(color=TEXT_COLOR, size=11),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.01,
            xanchor="right",
            x=1.0,
            font=dict(size=10, color=MUTED_COLOR),
            bgcolor="rgba(0,0,0,0)",
        ),
        xaxis=dict(
            title=dict(text=x_title, font=dict(size=11, color=MUTED_COLOR)) if x_title else None,
            gridcolor=GRID_COLOR,
            zeroline=False,
            showline=True,
            linecolor="#1E2532",
            tickfont=dict(color=MUTED_COLOR, size=10),
            automargin=True,
        ),
        yaxis=dict(
            title=dict(text=y_title, font=dict(size=11, color=MUTED_COLOR)) if y_title else None,
            gridcolor=GRID_COLOR,
            zeroline=False,
            showline=True,
            linecolor="#1E2532",
            tickfont=dict(color=MUTED_COLOR, size=10),
            automargin=True,
        ),
    )
    return fig


def _prep_df(history: list[dict[str, Any]]) -> pd.DataFrame:
    if not history:
        return pd.DataFrame()
    df = pd.DataFrame(history)
    if "recorded_at" in df.columns:
        df["recorded_at_dt"] = pd.to_datetime(df["recorded_at"], format="ISO8601", errors="coerce")
        df = df.sort_values("recorded_at_dt")
    elif "predicted_at" in df.columns:
        df["predicted_at_dt"] = pd.to_datetime(df["predicted_at"], format="ISO8601", errors="coerce")
        df = df.sort_values("predicted_at_dt")
    return df


def motor_temperature_chart(history: list[dict[str, Any]], height: int = 310) -> go.Figure:
    df = _prep_df(history)
    fig = go.Figure()
    if not df.empty:
        for lift_id, grp in df.groupby("lift_id"):
            col = LIFT_COLORS.get(str(lift_id), COBALT)
            fig.add_trace(
                go.Scatter(
                    x=grp["recorded_at_dt"],
                    y=grp["motor_temp"],
                    mode="lines",
                    name=str(lift_id),
                    line=dict(width=2.2, color=col),
                    fill="tozeroy" if df["lift_id"].nunique() == 1 else None,
                    fillcolor="rgba(37, 99, 235, 0.14)",
                    hovertemplate="%{y:.2f} °C<extra>%{fullData.name}</extra>",
                )
            )
    warn_val = SENSOR_METADATA["motor_temp"]["warning_high"]
    crit_val = SENSOR_METADATA["motor_temp"]["critical_high"]
    fig.add_hline(y=warn_val, line_dash="dash", line_color=AMBER, line_width=1.2, annotation_text=f"Warn {warn_val}°C")
    fig.add_hline(y=crit_val, line_dash="dot", line_color=CRIMSON, line_width=1.2, annotation_text=f"Crit {crit_val}°C")
    return _apply_black_layout(fig, "Traction Motor Temperature Profile", "Temperature (°C)", height=height)


def lift_operating_performance_chart(history: list[dict[str, Any]], height: int = 310) -> go.Figure:
    df = _prep_df(history)
    fig = go.Figure()
    if not df.empty:
        recent = df.tail(18)
        fig.add_trace(
            go.Bar(
                x=recent["recorded_at_dt"],
                y=recent["travel_time"],
                name="Travel Time (s)",
                marker_color=COBALT,
                hovertemplate="%{y:.2f} s<extra>Travel Time</extra>",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=recent["recorded_at_dt"],
                y=recent["door_cycle_time"],
                mode="lines+markers",
                name="Door Cycle (s)",
                line=dict(color=TEAL, width=2),
                marker=dict(size=5),
                hovertemplate="%{y:.2f} s<extra>Door Cycle</extra>",
            )
        )
    fig.add_hline(y=SENSOR_METADATA["travel_time"]["warning_high"], line_dash="dot", line_color=CRIMSON, line_width=1.1, annotation_text="Travel Warn 14.5s")
    fig.add_hline(y=SENSOR_METADATA["door_cycle_time"]["warning_high"], line_dash="dash", line_color=AMBER, line_width=1.0, annotation_text="Door Warn 4.6s")
    return _apply_black_layout(fig, "Trip Cycle & Door Response Performance", "Seconds (s)", height=height)


def vibration_chart(history: list[dict[str, Any]], height: int = 265) -> go.Figure:
    df = _prep_df(history)
    fig = go.Figure()
    if not df.empty:
        for lift_id, grp in df.groupby("lift_id"):
            fig.add_trace(
                go.Scatter(
                    x=grp["recorded_at_dt"],
                    y=grp["vibration_level"],
                    mode="lines",
                    name=str(lift_id),
                    line=dict(width=2, color=LIFT_COLORS.get(str(lift_id), TEAL)),
                    fill="tozeroy" if df["lift_id"].nunique() == 1 else None,
                    fillcolor="rgba(20, 184, 166, 0.14)",
                    hovertemplate="%{y:.2f} mm/s<extra>%{fullData.name}</extra>",
                )
            )
    fig.add_hline(y=SENSOR_METADATA["vibration_level"]["warning_high"], line_dash="dash", line_color=AMBER, line_width=1.1, annotation_text="Warn 3.5")
    fig.add_hline(y=SENSOR_METADATA["vibration_level"]["critical_high"], line_dash="dot", line_color=CRIMSON, line_width=1.1, annotation_text="Crit 5.0")
    return _apply_black_layout(fig, "Mechanical Vibration Level", "Vibration (mm/s)", height=height)


def door_cycle_chart(history: list[dict[str, Any]], height: int = 265) -> go.Figure:
    df = _prep_df(history)
    fig = go.Figure()
    if not df.empty:
        for lift_id, grp in df.groupby("lift_id"):
            fig.add_trace(
                go.Scatter(
                    x=grp["recorded_at_dt"],
                    y=grp["door_cycle_time"],
                    mode="lines",
                    name=str(lift_id),
                    line=dict(width=2, shape="hv", color=LIFT_COLORS.get(str(lift_id), AMBER)),
                    hovertemplate="%{y:.2f} s<extra>%{fullData.name}</extra>",
                )
            )
    fig.add_hline(y=SENSOR_METADATA["door_cycle_time"]["warning_high"], line_dash="dash", line_color=AMBER, line_width=1.1, annotation_text="Warn 4.6s")
    fig.add_hline(y=SENSOR_METADATA["door_cycle_time"]["critical_high"], line_dash="dot", line_color=CRIMSON, line_width=1.1, annotation_text="Crit 5.8s")
    return _apply_black_layout(fig, "Door Open/Close Cycle Time", "Seconds (s)", height=height)


def motor_current_chart(history: list[dict[str, Any]], height: int = 265) -> go.Figure:
    df = _prep_df(history)
    fig = go.Figure()
    if not df.empty:
        for lift_id, grp in df.groupby("lift_id"):
            fig.add_trace(
                go.Scatter(
                    x=grp["recorded_at_dt"],
                    y=grp["motor_current"],
                    mode="lines",
                    name=str(lift_id),
                    line=dict(width=2, color=LIFT_COLORS.get(str(lift_id), COBALT)),
                    hovertemplate="%{y:.2f} A<extra>%{fullData.name}</extra>",
                )
            )
    fig.add_hline(y=SENSOR_METADATA["motor_current"]["warning_high"], line_dash="dash", line_color=AMBER, line_width=1.1, annotation_text="Warn 33A")
    fig.add_hline(y=SENSOR_METADATA["motor_current"]["critical_high"], line_dash="dot", line_color=CRIMSON, line_width=1.1, annotation_text="Crit 39A")
    return _apply_black_layout(fig, "Traction Motor Current Draw", "Current (Amps)", height=height)


def cabin_load_chart(history: list[dict[str, Any]], height: int = 265) -> go.Figure:
    df = _prep_df(history)
    fig = go.Figure()
    if not df.empty:
        for lift_id, grp in df.groupby("lift_id"):
            fig.add_trace(
                go.Bar(
                    x=grp["recorded_at_dt"],
                    y=grp["cabin_load"],
                    name=str(lift_id),
                    marker_color=LIFT_COLORS.get(str(lift_id), COBALT),
                    opacity=0.85,
                    hovertemplate="%{y:.0f} kg<extra>%{fullData.name}</extra>",
                )
            )
    fig.add_hline(y=SENSOR_METADATA["cabin_load"]["warning_high"], line_dash="dash", line_color=AMBER, line_width=1.1, annotation_text="Heavy 920kg")
    fig.add_hline(y=SENSOR_METADATA["cabin_load"]["critical_high"], line_dash="dot", line_color=CRIMSON, line_width=1.1, annotation_text="Overload 1020kg")
    return _apply_black_layout(fig, "Cabin Payload Distribution", "Load (kg)", height=height)


def travel_time_chart(history: list[dict[str, Any]], height: int = 265) -> go.Figure:
    df = _prep_df(history)
    fig = go.Figure()
    if not df.empty:
        for lift_id, grp in df.groupby("lift_id"):
            fig.add_trace(
                go.Scatter(
                    x=grp["recorded_at_dt"],
                    y=grp["travel_time"],
                    mode="lines",
                    name=str(lift_id),
                    line=dict(width=2, color=LIFT_COLORS.get(str(lift_id), TEAL)),
                    hovertemplate="%{y:.2f} s<extra>%{fullData.name}</extra>",
                )
            )
    fig.add_hline(y=SENSOR_METADATA["travel_time"]["warning_high"], line_dash="dash", line_color=AMBER, line_width=1.1, annotation_text="Warn 14.5s")
    fig.add_hline(y=SENSOR_METADATA["travel_time"]["critical_high"], line_dash="dot", line_color=CRIMSON, line_width=1.1, annotation_text="Crit 17.0s")
    return _apply_black_layout(fig, "Floor-to-Floor Travel Time", "Seconds (s)", height=height)


def breakdown_bullet_chart(probability: float, threshold: float = 0.70, lift_id: str = "LIFT-01") -> go.Figure:
    pct = round(probability * 100.0, 1)
    bar_color = CRIMSON if probability >= 0.90 else (AMBER if probability >= threshold else (COBALT if probability >= 0.40 else EMERALD))
    fig = go.Figure(
        go.Indicator(
            mode="number+gauge",
            value=pct,
            number={"suffix": "%", "font": {"size": 28, "color": "#FFFFFF"}},
            title={"text": f"{lift_id}", "font": {"size": 12, "color": MUTED_COLOR}},
            gauge={
                "shape": "bullet",
                "axis": {"range": [0, 100], "tickcolor": MUTED_COLOR, "tickfont": {"size": 10}},
                "threshold": {"line": {"color": "#FFFFFF", "width": 2.5}, "thickness": 0.9, "value": round(threshold * 100.0, 1)},
                "bgcolor": "#121722",
                "bordercolor": "#1E2532",
                "borderwidth": 1,
                "steps": [
                    {"range": [0, 40], "color": "rgba(34, 197, 94, 0.14)"},
                    {"range": [40, 70], "color": "rgba(37, 99, 235, 0.16)"},
                    {"range": [70, 90], "color": "rgba(245, 158, 11, 0.18)"},
                    {"range": [90, 100], "color": "rgba(239, 68, 68, 0.22)"},
                ],
                "bar": {"color": bar_color, "thickness": 0.55},
            },
        )
    )
    fig.update_layout(
        height=135,
        margin=dict(l=72, r=24, t=28, b=28),
        paper_bgcolor=PAPER_BG,
        font=dict(color=TEXT_COLOR),
    )
    return fig


def contributing_factors_diverging_chart(factors: list[dict[str, Any]]) -> go.Figure:
    ordered = sorted(factors, key=lambda x: x.get("z_score", 0.0))
    labels = [f.get("label", f.get("feature", "")) for f in ordered]
    z_vals = [float(f.get("z_score", 0.0)) for f in ordered]
    colors = [CRIMSON if z >= 2.0 else (AMBER if z >= 0.75 else (COBALT if z <= -0.75 else "#475569")) for z in z_vals]

    fig = go.Figure(
        go.Bar(
            x=z_vals,
            y=labels,
            orientation="h",
            marker_color=colors,
            hovertemplate="Z-Score: %{x:.2f}<extra>%{y}</extra>",
        )
    )
    fig.add_vline(x=0.0, line_color="#475569", line_width=1.2)
    fig.add_vline(x=2.0, line_dash="dash", line_color=CRIMSON, line_width=1.0, annotation_text="Anomaly +2σ")
    return _apply_black_layout(
        fig,
        "Sensor Deviation from Healthy Baseline (Z-Score)",
        y_title="",
        x_title="Standard Deviations from Baseline (σ)",
        height=280,
    )


def breakdown_probability_trend_chart(
    pred_history: list[dict[str, Any]],
    threshold: float = 0.70,
    height: int = 275,
) -> go.Figure:
    df = _prep_df(pred_history)
    fig = go.Figure()
    if not df.empty:
        df["prob_pct"] = df["breakdown_probability"] * 100.0
        for lift_id, grp in df.groupby("lift_id"):
            fig.add_trace(
                go.Scatter(
                    x=grp["predicted_at_dt"],
                    y=grp["prob_pct"],
                    mode="lines",
                    name=str(lift_id),
                    line=dict(width=2, shape="hv", color=LIFT_COLORS.get(str(lift_id), COBALT)),
                    hovertemplate="%{y:.1f}%<extra>%{fullData.name}</extra>",
                )
            )
    fig.add_hline(
        y=round(threshold * 100.0, 1),
        line_dash="dash",
        line_color=CRIMSON,
        line_width=1.2,
        annotation_text=f"Alert Threshold ({threshold*100:.0f}%)",
    )
    return _apply_black_layout(fig, "Predicted 24h Breakdown Probability Timeline", "Probability (%)", height=height)


def confusion_matrix_chart(cm_data: dict[str, Any]) -> go.Figure:
    z = cm_data["matrix"]
    labels = cm_data.get("labels", ["No Breakdown (0)", "Breakdown <=24h (1)"])
    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=[f"Pred: {l}" for l in labels],
            y=[f"Actual: {l}" for l in labels],
            text=[[str(val) for val in row] for row in z],
            texttemplate="%{text}",
            textfont={"size": 16, "color": "#FFFFFF"},
            colorscale=[[0.0, "#121722"], [1.0, "#2563EB"]],
            showscale=False,
        )
    )
    fig.update_layout(
        title=dict(text="Confusion Matrix (Test Holdout Split)", font=dict(size=13, color="#FFFFFF"), x=0.01),
        height=310,
        margin=dict(l=20, r=20, t=50, b=40),
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=PLOT_BG,
        font=dict(color=TEXT_COLOR, size=11),
        xaxis=dict(automargin=True, tickfont=dict(color=MUTED_COLOR, size=10)),
        yaxis=dict(autorange="reversed", automargin=True, tickfont=dict(color=MUTED_COLOR, size=10)),
    )
    return fig


def feature_importance_chart(importances: list[dict[str, Any]]) -> go.Figure:
    ordered = sorted(importances, key=lambda x: x["importance"])
    labels = [SENSOR_METADATA.get(item["feature"], {}).get("label", item["feature"]) for item in ordered]
    values = [round(float(item["importance"]) * 100.0, 2) for item in ordered]
    fig = go.Figure(
        go.Bar(
            x=values,
            y=labels,
            orientation="h",
            marker_color=COBALT,
            hovertemplate="%{x:.2f}%<extra>%{y}</extra>",
        )
    )
    return _apply_black_layout(
        fig,
        "Random Forest Feature Importance",
        y_title="",
        x_title="Relative Weight (%)",
        height=310,
    )
