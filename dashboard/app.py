"""Main Streamlit entrypoint for Apartment Lift Breakdown Predictor (Pure-Black Spaced Top-Nav UI)."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.api_client import BackendClient
from dashboard.components.layout import render_command_header, render_html
from dashboard.views import (
    alert_center,
    breakdown_prediction,
    email_settings,
    lift_monitoring,
    model_performance,
    overview,
    sensor_analytics,
    system_settings,
)

st.set_page_config(
    page_title="Apartment Lift Breakdown Predictor",
    layout="wide",
    initial_sidebar_state="collapsed",
)

CSS_PATH = Path(__file__).resolve().parent / "styles" / "theme.css"
if CSS_PATH.exists():
    st.markdown(f"<style>{CSS_PATH.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)

# Elevator-specific navigation titles (distinct from ServerRoomACPredictor)
NAV_SECTIONS = [
    ("Fleet Pulse", "Fleet Pulse"),
    ("Shaft Telemetry", "Shaft Telemetry"),
    ("Fault Forecast", "Fault Forecast"),
    ("Load & Drift", "Load & Drift"),
    ("Incident Log", "Incident Log"),
    ("ML Diagnostics", "ML Diagnostics"),
    ("Dispatch Mail", "Dispatch Mail"),
    ("Control Deck", "Control Deck"),
]

LIVE_AUTO_REFRESH_PAGES = {
    "Fleet Pulse",
    "Shaft Telemetry",
    "Fault Forecast",
    "Incident Log",
}


def main() -> None:
    client = BackendClient()
    if "operator_key" not in st.session_state:
        st.session_state["operator_key"] = ""
    if "operator_unlocked" not in st.session_state:
        st.session_state["operator_unlocked"] = False
    if "active_page" not in st.session_state:
        st.session_state["active_page"] = "Fleet Pulse"

    ok_sys, sys_status = client.get_system_status()
    ok_lifts, lifts = client.list_lifts()
    lift_options = ["All Lifts"] + [l["lift_id"] for l in lifts] if (ok_lifts and lifts) else ["All Lifts", "LIFT-01", "LIFT-02", "LIFT-03"]

    settings = (sys_status or {}).get("settings", {}) if ok_sys else {}
    refresh_seconds = max(1, int(float(settings.get("dashboard_refresh_seconds", "3"))))
    selected_page = st.session_state["active_page"]
    if selected_page not in {k for k, _ in NAV_SECTIONS}:
        selected_page = "Fleet Pulse"
        st.session_state["active_page"] = selected_page
    operator_unlocked = bool(st.session_state.get("operator_unlocked"))

    # Clean borderless top navigation bar wrapped in keyed container for CSS targeting
    with st.container(key="top_nav_bar"):
        nav_cols = st.columns([0.95, 1.15, 1.05, 1.0, 0.95, 1.1, 1.05, 1.0, 1.05, 0.85], gap="small")

        for idx, (page_key, label) in enumerate(NAV_SECTIONS):
            with nav_cols[idx]:
                btn_type = "primary" if selected_page == page_key else "secondary"
                if st.button(label, key=f"topnav_{page_key}", type=btn_type, width="stretch"):
                    st.session_state["active_page"] = page_key
                    st.rerun()

        with nav_cols[8]:
            selected_lift = st.selectbox(
                "Lift Scope",
                options=lift_options,
                index=0,
                key="lift_scope",
                label_visibility="collapsed",
            )
        with nav_cols[9]:
            auto_refresh = st.checkbox(f"Live ({refresh_seconds}s)", value=True, key="auto_refresh_toggle")

    if operator_unlocked:
        c_lock, _ = st.columns([1.4, 8.6])
        with c_lock:
            if st.button("Lock Operator Session", width="stretch"):
                st.session_state["operator_key"] = ""
                st.session_state["operator_unlocked"] = False
                st.rerun()

    page_renderers = {
        "Fleet Pulse": overview.render,
        "Shaft Telemetry": lift_monitoring.render,
        "Fault Forecast": breakdown_prediction.render,
        "Load & Drift": sensor_analytics.render,
        "Incident Log": alert_center.render,
        "ML Diagnostics": model_performance.render,
        "Dispatch Mail": email_settings.render,
        "Control Deck": system_settings.render,
    }

    renderer = page_renderers[selected_page]

    if selected_page in LIVE_AUTO_REFRESH_PAGES and auto_refresh:
        @st.fragment(run_every=refresh_seconds)
        def _live_view() -> None:
            live_ok, live_status = client.get_system_status()
            render_command_header(
                page_title=selected_page,
                sys_status=live_status if live_ok else sys_status,
                backend_ok=live_ok,
                selected_lift=selected_lift,
                operator_unlocked=operator_unlocked,
            )
            renderer(client, selected_lift, live_status if live_ok else sys_status)

        _live_view()
    else:
        render_command_header(
            page_title=selected_page,
            sys_status=sys_status if ok_sys else None,
            backend_ok=ok_sys,
            selected_lift=selected_lift,
            operator_unlocked=operator_unlocked,
        )
        renderer(client, selected_lift, sys_status if ok_sys else None)


if __name__ == "__main__":
    main()
