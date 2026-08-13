# Wafer Yield Intelligence — Test Optimization Floor

Production-grade real-time dashboard for semiconductor ATE test optimization.

**Telemetry authority is the Python backend.** React only renders server projections over REST + WebSocket.

```
ATE / STDF / Test Logs
        ↓
Python Ingestion Service
        ↓
Validation → Normalization
        ↓
PostgreSQL
        ↓
Redis Event Bus
        ↓
FastAPI WebSocket Gateway (/ws/test-floor)
        ↓
Next.js React Application
```

## Stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js, React, TypeScript, Tailwind, Zustand, TanStack Query, Recharts |
| Backend | FastAPI, Pydantic, SQLAlchemy, PostgreSQL, Redis, WebSocket |
| ML | scikit-learn RUL estimator for predictive maintenance |

## Quick start (Windows)

### 1. Redis

```powershell
redis-server
```

### 2. PostgreSQL

**Option A — embedded (no system password needed):**

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\start_embedded_pg.py
```

Uses `postgresql+asyncpg://wafer_yield:wafer_yield@127.0.0.1:55432/wafer_yield`.

**Option B — docker-compose** (if Docker is available) or your local Postgres 16 — set `DATABASE_URL` in `backend/.env`.

### 3. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\pip.exe install -r requirements.txt
copy .env.example .env   # if needed
.\.venv\Scripts\python.exe -m app.ingestion.seed
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Optional **development-only** floor simulator (never mixed into production services):

```powershell
.\.venv\Scripts\python.exe -m simulation.floor_sim --count 5
```

Enterprise validation:

```powershell
$env:PYTHONPATH = (Get-Location).Path
.\.venv\Scripts\python.exe scripts\validate_enterprise_e2e.py
.\.venv\Scripts\python.exe scripts\test_auth_hardening.py
```

- API docs: http://127.0.0.1:8000/docs  
- Health: http://127.0.0.1:8000/api/health  
- Ready: http://127.0.0.1:8000/api/ready  
- WebSocket: ws://127.0.0.1:8000/ws/test-floor?token=<JWT>  

### 4. Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

## Deploy (Vercel UI + Hugging Face API)

**Recommended split for this project:**

| Layer | Host |
|-------|------|
| Next.js UI | **Vercel** (`frontend/`) |
| FastAPI + WebSocket | **Hugging Face Spaces** (Docker, `backend/`) |

See [DEPLOY-HUGGINGFACE.md](./DEPLOY-HUGGINGFACE.md).

Vercel env after Space is live:

```
NEXT_PUBLIC_API_BASE_URL=https://YOUR_HF_USER-wafer-yield-api.hf.space/api
NEXT_PUBLIC_WS_URL=wss://YOUR_HF_USER-wafer-yield-api.hf.space/ws/test-floor
```

Other options: [DEPLOY-VERCEL.md](./DEPLOY-VERCEL.md) (Render/Railway) · [DEPLOY.md](./DEPLOY.md) (Docker Compose)
## API surface

| Method | Path |
|--------|------|
| POST | `/api/telemetry/events` |
| GET | `/api/dashboard/summary` |
| GET | `/api/wafers` |
| GET | `/api/wafers/{wafer_id}` |
| GET | `/api/wafers/{wafer_id}/dies` |
| GET | `/api/kpis` |
| GET | `/api/events` |
| GET | `/api/testers` |
| GET | `/api/maintenance` |
| GET | `/api/test-limits` |
| WS | `/ws/test-floor` |

Every telemetry event includes: `event_id`, `event_type`, `timestamp`, `source`, `tester_id`, `site_id`, `lot_id`, `wafer_id`, `die_id`, `sequence_number`, `payload`.

## Rules

- No `Math.random()` business metrics in the React app
- No fake client `setInterval` metric generators
- No hardcoded production KPIs in components — values come from API
- Loading / empty / error / disconnected states are implemented
