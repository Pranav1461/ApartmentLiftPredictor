"""Tests for lift alert engine, deduplication, cooldown, Fernet encryption, and Gmail SMTP."""

from __future__ import annotations

import logging
import smtplib
from unittest.mock import patch

from alerts.alert_service import AlertEngine
from alerts.email_service import EmailService
from security.credential_encryption import decrypt_secret, encrypt_secret, mask_secret


def test_fernet_encryption_roundtrip(isolated_env) -> None:
    secret = "abcd efgh ijkl mnop"
    token = encrypt_secret(secret)
    assert secret not in token
    assert decrypt_secret(token) == secret
    assert "abcd" not in mask_secret(token)


def test_alert_deduplication_cooldown_and_resolution(isolated_env) -> None:
    db = isolated_env["db"]
    email_svc = EmailService(db)
    engine = AlertEngine(db, email_svc)

    db.save_email_settings(
        sender_email="sender@gmail.com",
        recipient_email="ops@example.com",
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        use_starttls=True,
        enabled=True,
        encrypted_app_password=encrypt_secret("test-app-password"),
    )

    high_pred = {
        "breakdown_probability": 0.85,
        "predicted_class": 1,
        "risk_level": "High",
        "contributing_factors": [{"label": "Motor Temperature", "value": 84.0, "unit": "°C"}],
    }
    reading = {
        "recorded_at": "2026-11-26T06:00:00+00:00",
        "motor_temp": 84.0,
        "vibration_level": 4.8,
        "door_cycle_time": 5.2,
        "motor_current": 37.5,
        "cabin_load": 550.0,
        "travel_time": 16.0,
    }
    pred_id_1 = db.insert_prediction(
        {
            "lift_id": "LIFT-01",
            "breakdown_probability": 0.85,
            "predicted_class": 1,
            "risk_level": "High",
            "contributing_factors": [],
            "model_version": "rf-lift-v1",
        }
    )

    with patch("alerts.email_service._send_smtp_message") as mock_smtp:
        a1 = engine.evaluate_prediction("LIFT-01", pred_id_1, high_pred, reading)
        assert a1 is not None
        assert a1["status"] == "active"
        assert a1["email_delivery_status"] == "sent"
        assert mock_smtp.call_count == 1

        pred_id_2 = db.insert_prediction(
            {
                "lift_id": "LIFT-01",
                "breakdown_probability": 0.92,
                "predicted_class": 1,
                "risk_level": "Critical",
                "contributing_factors": [],
                "model_version": "rf-lift-v1",
            }
        )
        high_pred_2 = dict(high_pred, breakdown_probability=0.92, risk_level="Critical")
        a2 = engine.evaluate_prediction("LIFT-01", pred_id_2, high_pred_2, reading)
        assert a2 is not None
        assert a2["id"] == a1["id"]
        assert len(db.list_alerts(lift_id="LIFT-01")) == 1
        assert mock_smtp.call_count == 1

        db.transition_alert_status(a1["id"], "acknowledged", actor="op", notes="Inspecting sheave")
        db.transition_alert_status(a1["id"], "resolved", actor="op", notes="Replaced guide shoe")

        a3 = engine.evaluate_prediction("LIFT-01", pred_id_2, high_pred_2, reading)
        assert a3 is not None
        assert a3["id"] != a1["id"]
        assert a3["email_delivery_status"] == "cooldown_skipped"
        assert len(db.list_alerts(lift_id="LIFT-01")) == 2
        assert mock_smtp.call_count == 1


def test_smtp_failure_preserves_dashboard_alert_and_never_logs_secret(isolated_env, caplog) -> None:
    db = isolated_env["db"]
    email_svc = EmailService(db)
    engine = AlertEngine(db, email_svc)

    secret_pw = "super-secret-gmail-app-pw"
    db.save_email_settings(
        sender_email="sender@gmail.com",
        recipient_email="ops@example.com",
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        use_starttls=True,
        enabled=True,
        encrypted_app_password=encrypt_secret(secret_pw),
    )

    pred_id = db.insert_prediction(
        {
            "lift_id": "LIFT-02",
            "breakdown_probability": 0.91,
            "predicted_class": 1,
            "risk_level": "Critical",
            "contributing_factors": [],
            "model_version": "rf-lift-v1",
        }
    )

    with caplog.at_level(logging.DEBUG):
        with patch(
            "alerts.email_service._send_smtp_message",
            side_effect=smtplib.SMTPAuthenticationError(535, b"5.7.8 Username and Password not accepted"),
        ):
            alert = engine.evaluate_prediction(
                "LIFT-02",
                pred_id,
                {"breakdown_probability": 0.91, "predicted_class": 1, "risk_level": "Critical", "contributing_factors": []},
                {"motor_temp": 88.0},
            )
            ok_test, msg_test = email_svc.send_test_email()

    assert alert is not None
    assert alert["status"] == "active"
    assert alert["email_delivery_status"] == "failed"
    assert db.get_alert(alert["id"]) is not None
    assert ok_test is False
    assert "authentication failed" in msg_test.lower()
    assert secret_pw not in caplog.text
    assert secret_pw not in msg_test
    assert secret_pw not in (alert.get("email_error") or "")
