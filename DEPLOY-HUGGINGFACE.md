# Backend on Hugging Face Spaces (+ Vercel frontend)

You asked to deploy the backend on **Hugging Face**, not Render.

```
Vercel (Next.js UI)
        │
        ▼ HTTPS / WSS
Hugging Face Docker Space (FastAPI + WS)
  ├─ SQLite (/data)            — default
  └─ In-process event bus      — default (no Redis needed)
```

---

## 1. Create the Space

1. Open [huggingface.co/new-space](https://huggingface.co/new-space)
2. Fill in:
   - **Space name:** `wafer-yield-api` (or any name)
   - **SDK:** **Docker**
   - **Hardware:** CPU basic (free)
3. Create Space

---

## 2. Upload the backend

The Space root must be the **`backend/`** folder contents (Dockerfile + `app/` + README.md).

### Option A — Git (recommended)

```powershell
cd "c:\ate frondend\backend"
git init
git add .
git commit -m "Wafer Yield API for Hugging Face Spaces"
git branch -M main
git remote add origin https://huggingface.co/spaces/YOUR_HF_USER/wafer-yield-api
git push -u origin main
```

Use a [Hugging Face access token](https://huggingface.co/settings/tokens) with **Write** permission when prompted.

### Option B — Web UI

In the Space → **Files** → upload:

- `Dockerfile`
- `README.md`
- `requirements.txt`
- `alembic.ini`
- entire `app/` folder
- `alembic/` folder (optional)
- `scripts/` folder (optional)

---

## 3. Set secrets

Space → **Settings** → **Variables and secrets**:

| Name | Value |
|------|--------|
| `JWT_SECRET` | long random string |
| `CORS_ORIGINS` | `https://YOUR_VERCEL_APP.vercel.app,http://localhost:3000` |
| `AUTH_DISABLED` | `false` |

Optional: `DATABASE_URL` (Neon Postgres), `REDIS_URL` (Upstash).  
If omitted, Spaces uses **SQLite + memory bus** automatically.

---

## 4. Wait for build → test

Space URL looks like:

```
https://YOUR_HF_USER-wafer-yield-api.hf.space
```

Check:

```
https://YOUR_HF_USER-wafer-yield-api.hf.space/api/health
https://YOUR_HF_USER-wafer-yield-api.hf.space/api/ready
https://YOUR_HF_USER-wafer-yield-api.hf.space/docs
```

Login test:

```powershell
curl -X POST https://YOUR_HF_USER-wafer-yield-api.hf.space/api/auth/login `
  -H "Content-Type: application/json" `
  -d "{\"username\":\"viewer\",\"password\":\"viewer123\"}"
```

---

## 5. Connect Vercel frontend

In Vercel project → Environment Variables:

```
NEXT_PUBLIC_API_BASE_URL=https://YOUR_HF_USER-wafer-yield-api.hf.space/api
NEXT_PUBLIC_WS_URL=wss://YOUR_HF_USER-wafer-yield-api.hf.space/ws/test-floor
```

Redeploy the frontend after setting these.

---

## Notes

- Free Spaces can **sleep**; first request may be slow.
- WebSockets work on Docker Spaces via `wss://...hf.space/ws/test-floor`.
- Do not run `simulation.floor_sim` as production fab telemetry.
- For stronger persistence, attach Neon Postgres via `DATABASE_URL`.
