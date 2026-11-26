# Apartment Lift Breakdown Predictor

A predictive maintenance dashboard and alert system for apartment elevator (lift) equipment. It streams and monitors six correlated mechanical and electrical sensor metrics across multiple lifts (`LIFT-01`, `LIFT-02`, `LIFT-03`), checks data quality and baseline drift, predicts whether a lift is likely to break down within the next **24 hours**, and delivers deduplicated dashboard and **Gmail SMTP** email alerts before an unexpected outage occurs.

---

## Problem Statement & Objectives

Apartment elevators experience heavy rush-hour traffic and gradual wear across traction bearings, door operators, and motor windings. Basic fault trips usually trigger only after a lift stops running—stranding residents or taking a shaft offline unexpectedly.

**Primary Objectives:**
- Continuously generate and store six realistic elevator sensor metrics in SQLite.
- Train a leakage-free `RandomForestClassifier` pipeline (`SimpleImputer` + classifier) on a 24-hour lookahead target (`breakdown_within_24h`).
- Validate data quality (keeping genuine `0.0 kg` empty-cabin readings distinct from missing `NULL` readings) and flag baseline sensor drift.
- Run an independent background alert engine inside FastAPI that persists alerts and sends Gmail SMTP notifications even when no browser is open.
- Provide an industrial dark-theme Streamlit dashboard with live monitoring, risk forecasts, alert management, and encrypted Gmail SMTP configuration.
- Containerize the full stack with Docker Compose and provide a single-window Windows launcher (`setup.bat`).

---

## Tech Stack

| Layer | Tools Used |
|---|---|
| **Backend & API** | Python 3.13, FastAPI, Uvicorn, Pydantic |
| **Data & ML** | Pandas, NumPy, Scikit-learn (`Pipeline`, `SimpleImputer`, `RandomForestClassifier`), Joblib |
| **Database** | SQLite (WAL mode, indexed tables, Docker volume persistence) |
| **Dashboard** | Streamlit (`@st.fragment` auto-refresh), Plotly, Custom CSS |
| **Notifications & Security** | `cryptography.fernet` symmetric encryption, `smtplib` (Gmail `STARTTLS` port `587`), `email-validator` |
| **Deployment & Testing** | Docker, Docker Compose, `setup.bat`, `pytest`, `httpx` |

---

## System Architecture

```text
+-----------------------+       POST /sensors/ingest      +----------------------------------+
|  Lift Sensor Simulator| ------------------------------> |  FastAPI Backend (:8000)         |
|  (LIFT-01, 02, 03)    |                                 |  - Missing data & drift checks   |
+-----------------------+                                 |  - Joblib ML inference           |
                                                          |  - Background alert engine       |
                                                          |  - Gmail SMTP (STARTTLS)         |
                                                          +----------------+-----------------+
                                                                           |
                                                                  SQLite (WAL Volume)
                                                                           |
+-----------------------+        REST API (3s poll)       +----------------v-----------------+
|  Maintenance Inbox    | <------ Gmail SMTP (587) ------ |  Streamlit Dashboard (:8501)     |
|  (App Password Auth)  |                                 |  8 Views + Operator Access Gate  |
+-----------------------+                                 +----------------------------------+
```

---

## Monitored Sensor Metrics

| Sensor | Column | Unit | Normal Operating Range | Warning / Critical |
|---|---|---|---|---|
| **Motor Temperature** | `motor_temp` | °C | 40.0 – 68.0 °C | Warn ≥ 75.0 °C / Crit ≥ 85.0 °C |
| **Vibration Level** | `vibration_level` | mm/s | 0.3 – 2.5 mm/s | Warn ≥ 3.5 mm/s / Crit ≥ 5.0 mm/s |
| **Door Cycle Time** | `door_cycle_time` | s | 2.2 – 3.9 s | Warn ≥ 4.6 s / Crit ≥ 5.8 s |
| **Motor Current** | `motor_current` | A | 10.0 – 28.0 A | Warn ≥ 33.0 A / Crit ≥ 39.0 A |
| **Cabin Load** | `cabin_load` | kg | 0 – 850 kg | Warn ≥ 920 kg / Crit ≥ 1020 kg |
| **Travel Time** | `travel_time` | s | 7.5 – 12.8 s | Warn ≥ 14.5 s / Crit ≥ 17.0 s |

---

## Dataset, Target Labeling & Model Evaluation

### Historical Dataset (`ml/generate_dataset.py`)
- **Size**: `25,920` 15-minute rows across 90 days and 3 lifts (`LIFT-01`, `LIFT-02`, `LIFT-03`).
- **Behavior**: Simulates morning and evening residential rush-hour traffic, transient non-failing heavy-load bursts, and three gradual fault trajectories (`traction_bearing_wear`, `door_operator_fault`, `motor_winding_overload`).
- **Target Label (`breakdown_within_24h`)**: Set to `1` when a simulated breakdown event occurs within the future 24-hour window `(t, t + 24h]`, and `0` otherwise—preventing target leakage.
- **Missing Values**: Injects ~2.5% missing readings (`3,923` missing entries total) handled by `SimpleImputer(strategy="median")` inside the pipeline.

### Model Training & Evaluation (`ml/train_model.py`, `ml/models/model_evaluation.json`)
- **Split**: Chronological 75% / 25% split (`19,440` train / `6,480` test rows, cutoff `2026-03-09T12:00:00+00:00`) so readings from the same degradation episode do not leak from future intervals into training.
- **Observed Holdout Results (`rf-lift-predictor-v1.0`)**:
  - **Positive Prevalence**: `8.98%`
  - **Accuracy**: `97.61%` (`0.9761`)
  - **Precision**: `88.61%` (`0.8861`)
  - **Recall**: `84.19%` (`0.8419`)
  - **F1-Score**: `86.34%` (`0.8634`)
  - **ROC-AUC**: `0.9582` | **PR-AUC**: `0.8999`
  - **Confusion Matrix (`n = 6,480`)**: `TN = 5835`, `FP = 63`, `FN = 92`, `TP = 490`

**Why accuracy alone is insufficient:** Because breakdown events are uncommon (`8.98%` here, and often `<2%` in production), predicting "No Breakdown" for every sample yields ~91% accuracy with **0% recall**, missing every failure. Recall, Precision, F1-score, PR-AUC, and Confusion Matrix evaluation ensure real breakdowns are caught early without excessive false alarms.

### Risk Classification Tiers
| Breakdown Probability | Risk Level | Behavior |
|---|---|---|
| `< 40%` | **Low** | Normal monitoring |
| `40% to < 70%` | **Medium** | Lift status marked warning |
| `70% to < 90%` | **High** | Creates alert and sends email (default threshold `0.70`) |
| `>= 90%` | **Critical** | Critical alert and email notification |

---

## Quick Start (Windows One-Click Launcher)

Double-click **`setup.bat`**:
- Opens a single launcher CMD window while running all services in the background.
- Generates `.env` with a local Fernet encryption key if missing.
- Starts Docker Compose (`backend`, `simulator`, `dashboard`) if Docker is available (or falls back to hidden local Python processes), waits for health checks, and opens **http://localhost:8501**.

---

## Gmail SMTP & Security Setup

Never use your standard Gmail login password. Use a Google App Password:
1. Enable **2-Step Verification** on the sender Gmail account under Google Account → **Security**.
2. Go to **Security → App Passwords** and create a 16-character App Password.
3. Open **http://localhost:8501** → **Email Notification Settings**.
4. Unlock **Operator Authorization** with `OPERATOR_ACCESS_KEY` from `.env`.
5. Enter your Sender Gmail Address, 16-character App Password, Maintenance Recipient Email, `smtp.gmail.com`, Port `587`, and enable **STARTTLS** + **Enable Email Alert Notifications**.
6. Click **Save Configuration** and **Test Email Connection**.

### Credential & API Security
- App Passwords are encrypted using `cryptography.fernet.Fernet` before storage in SQLite.
- `CREDENTIALS_ENCRYPTION_KEY` is stored solely in `.env` / environment variables—never in SQLite or Git.
- Settings, lift fault mode, and email endpoints require `X-Operator-Key` verified with `hmac.compare_digest` against `OPERATOR_ACCESS_KEY`.
- Passwords are masked in the UI and stripped from API responses, validation error payloads (`SecretStr` + `RequestValidationError` redaction), and logs.

---

## API Endpoints (Swagger UI at `/docs`)

- **System**: `GET /api/v1/system/health`, `GET /api/v1/system/status`, `POST /api/v1/system/auth/verify`, `PUT /api/v1/system/settings`
- **Lifts**: `GET /api/v1/lifts`, `GET /api/v1/lifts/{lift_id}`, `GET /api/v1/lifts/{lift_id}/status`, `PUT /api/v1/lifts/{lift_id}/mode`
- **Sensors**: `GET /api/v1/sensors/latest`, `GET /api/v1/sensors/history`, `POST /api/v1/sensors/ingest`, `POST /api/v1/sensors/simulate-tick`, `GET /api/v1/sensors/drift`, `GET /api/v1/sensors/quality`
- **Predictions & Model**: `GET /api/v1/predictions/latest`, `GET /api/v1/predictions/history`, `GET /api/v1/model/performance`
- **Alerts**: `GET /api/v1/alerts`, `GET /api/v1/alerts/active`, `POST /api/v1/alerts/{alert_id}/acknowledge`, `POST /api/v1/alerts/{alert_id}/resolve`
- **Email**: `GET /api/v1/email/config`, `PUT /api/v1/email/config`, `PATCH /api/v1/email/toggle`, `POST /api/v1/email/test`

---

## Local Development & Deployment Runbook

### Local Python Setup
```bash
python -m venv .venv
# Windows: .venv\Scripts\Activate.ps1 | Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Paste the generated key into CREDENTIALS_ENCRYPTION_KEY and set OPERATOR_ACCESS_KEY in .env

python -m ml.generate_dataset
python -m ml.train_model
python -m pytest -v

uvicorn backend.main:app --host 0.0.0.0 --port 8000
python -m simulator.sensor_generator --api-url http://localhost:8000
streamlit run dashboard/app.py --server.port 8501
```

### Docker Operations Runbook
- **Start / rebuild services**: `docker compose up -d --build`
- **Stop services (keeps SQLite volume)**: `docker compose down`
- **Restart services**: `docker compose restart`
- **Check container health**: `docker compose ps` and `curl -f http://localhost:8000/api/v1/system/health`
- **Inspect logs**: `docker compose logs -f backend` (or `simulator`, `dashboard`)
- **Back up SQLite database & key**:
  ```bash
  docker compose exec backend python -c "import sqlite3; src=sqlite3.connect('/app/data/lift_predictor.db'); dst=sqlite3.connect('/app/data/backup.db'); src.backup(dst); dst.close(); src.close()"
  docker cp lift-predictor-backend:/app/data/backup.db ./lift_predictor_backup.db
  ```
  Store `.env` (`CREDENTIALS_ENCRYPTION_KEY`) in a separate secure backup; encrypted SMTP credentials cannot be decrypted without the matching Fernet key.

### Troubleshooting
- **No live sensor data**: Check `docker compose logs simulator` and ensure **Continuous Sensor Simulator Enabled** is on in **System Settings**.
- **Model inference error**: Confirm `ml/models/lift_breakdown_model.joblib` exists or keep `AUTO_TRAIN_IF_MISSING=true`.
- **SMTP `535 Authentication Failed`**: Verify 2-Step Verification is active on Gmail and a 16-character App Password is used. Persisted dashboard alerts are never deleted if SMTP fails.

---

## Known Limitations

1. **Synthetic Dataset**: Training trajectories are physics-based simulations rather than field elevator logs; production deployment requires retraining on real site data.
2. **Drift Detection**: Rolling baseline checks cannot isolate sensor calibration drift from sustained changes in building traffic or mechanical wear without physical inspection.
3. **Single Operator Key**: Configuration endpoints rely on a shared `OPERATOR_ACCESS_KEY` rather than multi-user RBAC.
