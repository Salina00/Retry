# Retry: B2B Revenue Recovery Agent Dashboard

**Retry** is an autonomous AI agent prototype designed for the **Razorpay AI Buildathon (Track: AI Revenue Recovery)**. It detects failed checkouts and overdue receivables (P2P), diagnoses their root causes via Anthropic's Claude 3.5 API, decides the optimal recovery action, validates operations against strict business compliance guardrails, and executes sandbox interventions, logging every step into an immutable, append-only audit trail.

---

## Technical Stack

- **Backend**: Python 3.13+, FastAPI, SQLite (local development fallback) / PostgreSQL (production), SQLAlchemy, Pydantic (structured validation)
- **AI**: Anthropic Claude API (tool-use/function calling, hand-coded orchestration loop, no agent frameworks)
- **Payments**: Razorpay Python SDK (Test Mode declination logic and webhook signatures)
- **Frontend**: Next.js 15, React, Tailwind CSS, Lucide icons, styled in Razorpay's native indigo-accent console language.

---

## Core Directory Structure

```text
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI entrypoint & webhook receiver
│   │   ├── config.py           # Settings and env validation
│   │   ├── db.py               # Database engine & session generator
│   │   ├── models.py           # SQLAlchemy tables (Case, AuditLogEntry, Action, etc.)
│   │   ├── schemas.py          # Pydantic schema constraints
│   │   ├── pipeline/           # 6-Stage agent sequence
│   │   │   ├── detection.py    # Webhook processor & simulator
│   │   │   ├── diagnosis.py    # AI Diagnosis agent (Claude API tool calling)
│   │   │   ├── decision.py     # AI Decision agent (Intervention generator)
│   │   │   ├── guardrails.py   # Python compliance checks
│   │   │   └── metrics.py      # Telemetry calculations
│   │   └── api/                # Endpoints (Cases, Batch, Metrics)
│   ├── eval/
│   │   ├── eval_set.json       # 20 hand-labeled golden cases
│   │   └── run_eval.py         # Diagnostic accuracy evaluator
│   └── requirements.txt        # Backend dependencies
└── frontend/
    ├── src/
    │   ├── app/                # NextJS layout, dashboard, cases, trace, simulation
    │   ├── components/         # Left sidebar navigation
    │   └── lib/                # API client connection logic
    └── package.json            # Frontend node packages
```

---

## Configuration & Environment Variables

Create a `.env` file inside the `backend` folder to configure the application.

```env
# Database configuration (defaults to local SQLite if left blank)
DATABASE_URL=postgresql://user:password@localhost:5432/dbname

# Anthropic AI configuration (necessary for active Claude AI diagnosis & decisions)
ANTHROPIC_API_KEY=your-anthropic-api-key-here

# Razorpay credentials (test mode defaults are set for mock verification)
RAZORPAY_KEY_ID=rzp_test_your_key_id
RAZORPAY_KEY_SECRET=rzp_test_your_key_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_signature_secret
```

---

## Setup & Running the Application

### 1. Backend Server Setup

Navigate to the project root directory and run the following:

```bash
# Verify you have Python 3.13 installed
python --version

# Install dependencies
pip install -r backend/requirements.txt

# Start the FastAPI server using uvicorn (defaults to port 8000)
# Setting PYTHONPATH allows Python to resolve the modules correctly
$env:PYTHONPATH="."
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Verify backend health by navigating to `http://127.0.0.1:8000/`.

### 2. Run Diagnostics Evaluation

Evaluate the accuracy of the recovery diagnosis model (either via local rule fallbacks or live Claude tool calls) against the 20 golden test sets:

```bash
$env:PYTHONPATH="."
python backend/eval/run_eval.py
```

### 3. Frontend Server Setup

Open a new terminal window:

```bash
# Navigate to the frontend directory
cd frontend

# Install Node modules
npm install

# Start the NextJS server (defaults to http://localhost:3000)
npm run dev
```

Open `http://localhost:3000` to view the Dashboard!

---

## Demo Walkthrough Guide

To test the system end-to-end, follow these three steps:

### Step 1: Seed the Database
Navigate to **Simulation Control** in the sidebar. Enter a number (e.g. `15`) and click **Clear & Seed Events**. This will flush the database and trigger 15 new payment failures, generating full 6-stage pipeline traces (some recovered, some blocked, some executed).

### Step 2: Test the Time Gated Guardrail (`is_within_calling_window`)
1. Click **Time Travel Presets: Night (10:00 PM)**. The console will report time-traveling to night and executing a tick.
2. Go to **Cases**, filter by status **Decided** or **Blocked**. Open a case details view.
3. You will see that in **Stage 4 (Guardrails)**, `is_within_calling_window()` has failed because 10 PM is outside the valid 8 AM - 7 PM window.
4. The recovery email or SMS action is currently marked as **Pending** in Stage 5, waiting for the window to open.
5. Go back to **Simulation Control** and click **Morning (10:00 AM)**. The scheduler tick will execute, releasing the queued pending actions! Open the case details again to see that they have successfully transitioned to `executed` with sandbox outputs.

### Step 3: Test Promise-to-Pay Reactivation
1. Navigate to **Cases** and find an active case with leak type **B2B Promise-to-Pay** (or status *Actioned*).
2. Click **Log Promise-to-Pay**. Enter tomorrow's date and a promise amount, then submit. The case will log a pending promise.
3. Go back to **Simulation Control** and click **Time Travel Presets: +5 Days Future**.
4. The scheduler sweeps, detects that the promise date has passed without payment reconciliation, marks the promise status as `broken`, logs the broken promise, and reactivates the recovery sequence automatically, dispatching a new dunning email!
