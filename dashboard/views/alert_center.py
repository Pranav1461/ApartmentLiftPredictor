"""Alert Center page with architectural timeline feed, filters, search, and resolution controls."""

from __future__ import annotations

import html
from typing import Any

import streamlit as st

from dashboard.api_client import BackendClient
from dashboard.components.layout import (
    format_timestamp,
    render_html,
    render_metric_bar,
    render_section_label,
    status_pill_html,
)


def render(client: BackendClient, selected_lift: str, sys_status: dict[str, Any] | None) -> None:
    lift_param = None if selected_lift == "All Lifts" else selected_lift
    ok_all, all_alerts = client.list_alerts(lift_id=lift_param, limit=250)
    if not ok_all:
        st.error(f"Unable to fetch alerts: {all_alerts}")
        return

    alerts_list: list[dict[str, Any]] = all_alerts or []
    active_cnt = sum(1 for a in alerts_list if a["status"] == "active")
    ack_cnt = sum(1 for a in alerts_list if a["status"] == "acknowledged")
    crit_cnt = sum(1 for a in alerts_list if a["status"] in ("active", "acknowledged") and a["severity"] == "critical")
    resolved_cnt = sum(1 for a in alerts_list if a["status"] == "resolved")

    render_metric_bar(
        [
            {"label": "Active Alerts", "value": str(active_cnt), "sub": "Unacknowledged incidents", "tone": "crit" if active_cnt > 0 else "ok"},
            {"label": "Acknowledged", "value": str(ack_cnt), "sub": "Under technician review", "tone": "warn" if ack_cnt > 0 else "ok"},
            {"label": "Open Critical", "value": str(crit_cnt), "sub": "Breakdown risk >= 90%", "tone": "crit" if crit_cnt > 0 else "ok"},
            {"label": "Resolved Incidents", "value": str(resolved_cnt), "sub": "Closed in history", "tone": "ok"},
        ]
    )

    render_section_label("Filter & Search Incidents")
    f1, f2, f3 = st.columns([1.0, 1.0, 1.6])
    with f1:
        status_filter = st.selectbox("Status", options=["All", "open", "active", "acknowledged", "resolved"], index=0)
    with f2:
        severity_filter = st.selectbox("Severity", options=["All", "critical", "warning"], index=0)
    with f3:
        search_query = st.text_input("Search Alerts", placeholder="Filter by lift, title, or inspection action...").strip().lower()

    filtered = []
    for al in alerts_list:
        if status_filter == "open" and al["status"] not in ("active", "acknowledged"):
            continue
        if status_filter not in ("All", "open") and al["status"] != status_filter:
            continue
        if severity_filter != "All" and al["severity"] != severity_filter:
            continue
        if search_query:
            haystack = " ".join(
                [
                    str(al.get("lift_id", "")),
                    str(al.get("title", "")),
                    str(al.get("description", "")),
                    str(al.get("recommended_action", "")),
                ]
            ).lower()
            if search_query not in haystack:
                continue
        filtered.append(al)

    render_section_label(f"Incident Feed ({len(filtered)})")
    if not filtered:
        st.info("No alerts match the current filter criteria.")
        return

    for al in filtered:
        aid = al["id"]
        sev = al["severity"]
        st_val = al["status"]
        prob_pct = float(al["breakdown_probability"]) * 100.0
        cls = "timeline-item timeline-crit" if sev == "critical" else "timeline-item"

        sev_pill = status_pill_html(f"SEVERITY: {sev.upper()}", sev)
        stat_pill = status_pill_html(f"STATUS: {st_val.upper()}", st_val)
        err_suffix = f" — {html.escape(al['email_error'])}" if al.get("email_error") else ""

        render_html(
            f"""
            <div class="{cls}">
                <div style="display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:8px;">
                    <div>
                        <strong style="font-size:0.95rem; color:#FFFFFF;">#{aid} &middot; {html.escape(al['title'])}</strong>
                        <span style="color:#94A3B8; font-size:0.8rem; margin-left:8px;">
                            Lift: <strong style="color:#FFFFFF;">{html.escape(al['lift_id'])}</strong> | Risk: {html.escape(al['risk_level'])} ({prob_pct:.1f}%)
                        </span>
                    </div>
                    <div style="display:flex; gap:6px; align-items:center;">
                        {sev_pill}
                        {stat_pill}
                    </div>
                </div>
                <div style="font-size:0.84rem; color:#CBD5E1; margin-top:6px;">
                    {html.escape(al['description'])}
                </div>
                <div style="font-size:0.82rem; color:#F8FAFC; margin-top:6px;">
                    <strong>Recommended Inspection:</strong> {html.escape(al['recommended_action'])}
                </div>
                <div style="font-size:0.75rem; color:#8491A3; margin-top:6px;">
                    Created: {html.escape(format_timestamp(al.get('created_at')))} |
                    Email Delivery: <strong>{html.escape(al.get('email_delivery_status', 'pending'))}</strong>{err_suffix}
                </div>
            </div>
            """
        )

        if st_val in ("active", "acknowledged"):
            act_col1, act_col2, act_col3 = st.columns([2.2, 0.9, 0.9])
            with act_col1:
                note_val = st.text_input(
                    f"Operator Note (#{aid})",
                    key=f"alert_note_{aid}",
                    placeholder="Optional inspection or resolution note...",
                    label_visibility="collapsed",
                )
            with act_col2:
                if st_val == "active":
                    if st.button("Acknowledge", key=f"ack_btn_{aid}", width="stretch"):
                        ok, res = client.acknowledge_alert(aid, actor="operator", notes=note_val)
                        if ok:
                            st.success(f"Alert #{aid} acknowledged.")
                            st.rerun()
                        else:
                            st.error(str(res))
            with act_col3:
                if st.button("Resolve", key=f"res_btn_{aid}", type="primary", width="stretch"):
                    ok, res = client.resolve_alert(aid, actor="operator", notes=note_val)
                    if ok:
                        st.success(f"Alert #{aid} resolved.")
                        st.rerun()
                    else:
                        st.error(str(res))

        with st.expander(f"Triggering Sensor Snapshot (#{aid})", expanded=False):
            st.json(al.get("triggering_readings") or {})
