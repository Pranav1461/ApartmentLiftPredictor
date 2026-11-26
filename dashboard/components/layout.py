"""Pure-black OLED telemetry UI helpers for the Apartment Lift dashboard."""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any

import streamlit as st


def render_html(markup: str) -> None:
    """Render HTML cleanly via st.markdown without triggering CommonMark code blocks."""
    cleaned = " ".join(line.strip() for line in markup.splitlines() if line.strip())
    st.markdown(cleaned, unsafe_allow_html=True)


def format_timestamp(ts: str | None) -> str:
    if not ts:
        return "Waiting for telemetry"
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except ValueError:
        return ts


def status_pill_html(status_text: str, level: str = "info") -> str:
    """Render accessible status pill combining color and explicit geometric marker."""
    cls_map = {
        "ok": ("pill-ok", "●"),
        "operational": ("pill-ok", "●"),
        "low": ("pill-ok", "●"),
        "resolved": ("pill-ok", "●"),
        "warning": ("pill-warn", "▲"),
        "warn": ("pill-warn", "▲"),
        "medium": ("pill-warn", "▲"),
        "high": ("pill-warn", "▲"),
        "acknowledged": ("pill-info", "◆"),
        "critical": ("pill-crit", "■"),
        "crit": ("pill-crit", "■"),
        "active": ("pill-crit", "■"),
        "offline": ("pill-crit", "■"),
        "info": ("pill-info", "◆"),
    }
    css_cls, marker = cls_map.get(level.lower(), ("pill-info", "◆"))
    return f'<span class="pill {css_cls}">{marker} {html.escape(status_text)}</span>'


def render_command_header(
    page_title: str,
    sys_status: dict[str, Any] | None,
    backend_ok: bool,
    selected_lift: str,
    operator_unlocked: bool,
) -> None:
    """Render minimal pure-black top brand header with SVG emblem, sync timestamp, and status pills."""
    summary = (sys_status or {}).get("summary", {})
    active_alerts = int(summary.get("active_alerts", 0))
    last_update = format_timestamp((sys_status or {}).get("last_data_update"))

    conn_pill = status_pill_html("ONLINE", "ok") if backend_ok else status_pill_html("OFFLINE", "crit")
    alert_pill = (
        status_pill_html(f"{active_alerts} ACTIVE ALERTS", "crit")
        if active_alerts > 0
        else status_pill_html("0 ACTIVE ALERTS", "ok")
    )
    op_pill = status_pill_html("OPERATOR", "info") if operator_unlocked else status_pill_html("VIEWER", "info")

    emblem_svg = (
        '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">'
        '<path d="M12 2C17.5228 2 22 6.47715 22 12C22 17.5228 17.5228 22 12 22V2Z" fill="#FFFFFF"/>'
        '<rect x="3" y="5" width="4" height="14" rx="2" fill="#2563EB"/>'
        '</svg>'
    )

    render_html(
        f"""
        <div class="bms-header">
            <div class="bms-brand">
                {emblem_svg}
                <span class="bms-brand-code">/ lift-ops@elevate</span>
                <span class="bms-brand-title">{html.escape(page_title)}</span>
            </div>
            <div class="bms-meta-row">
                <span>Scope: <strong style="color:#FFFFFF;">{html.escape(selected_lift)}</strong></span>
                <span>Sync: <strong style="color:#FFFFFF;">{html.escape(last_update)}</strong></span>
                {conn_pill}
                {alert_pill}
                {op_pill}
            </div>
        </div>
        """
    )


def render_metric_bar(items: list[dict[str, str]]) -> None:
    """Render a clean 4-column horizontal metric strip."""
    cells = []
    for item in items:
        label = html.escape(str(item.get("label", "")))
        value = html.escape(str(item.get("value", "--")))
        sub = html.escape(str(item.get("sub", "")))
        tone = item.get("tone", "")
        color_css = ""
        if tone == "crit":
            color_css = ' style="color:#F87171;"'
        elif tone == "warn":
            color_css = ' style="color:#FBBF24;"'
        elif tone == "ok":
            color_css = ' style="color:#4ADE80;"'

        cells.append(
            f'<div class="metric-slot">'
            f'<div class="metric-title">{label}</div>'
            f'<div class="metric-num"{color_css}>{value}</div>'
            f'<div class="metric-foot">{sub}</div>'
            f'</div>'
        )
    render_html(f'<div class="metric-bar">{"".join(cells)}</div>')


def render_section_label(title: str) -> None:
    render_html(f'<div class="sec-label">{html.escape(title)}</div>')


def render_sensor_meter(
    label: str,
    value: float | None,
    unit: str,
    warn_high: float,
    crit_high: float,
    max_scale: float,
    decimals: int = 1,
) -> None:
    """Render a clean horizontal threshold meter bar for a live sensor value."""
    if value is None:
        val_text = "MISSING"
        pct = 0.0
        fill_color = "#64748B"
        pill = status_pill_html("MISSING", "warn")
    else:
        val_text = f"{value:.{decimals}f} {unit}"
        pct = min(max((value / max(max_scale, 1e-6)) * 100.0, 2.0), 100.0)
        if value >= crit_high:
            fill_color = "#EF4444"
            pill = status_pill_html("CRITICAL", "crit")
        elif value >= warn_high:
            fill_color = "#F59E0B"
            pill = status_pill_html("WARNING", "warn")
        else:
            fill_color = "#2563EB"
            pill = status_pill_html("NOMINAL", "ok")

    render_html(
        f"""
        <div class="sensor-meter">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:0.8rem; font-weight:600; color:#CBD5E1;">{html.escape(label)}</span>
                {pill}
            </div>
            <div style="display:flex; justify-content:space-between; align-items:baseline; margin-top:6px;">
                <span style="font-size:1.2rem; font-weight:700; color:#FFFFFF;">{html.escape(val_text)}</span>
                <span style="font-size:0.72rem; color:#8491A3;">Warn {warn_high} / Crit {crit_high} {html.escape(unit)}</span>
            </div>
            <div class="progress-track">
                <div class="progress-fill" style="width:{pct:.1f}%; background-color:{fill_color};"></div>
            </div>
        </div>
        """
    )
