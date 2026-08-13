---
title: Wafer Yield Intelligence API
emoji: 🏭
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
base_path: /docs
pinned: false
license: mit
---

# Wafer Yield Intelligence API (Hugging Face Space)

FastAPI backend for the semiconductor test optimization platform.

## Endpoints

| Path | Purpose |
|------|---------|
| `/api/health` | Liveness |
| `/api/ready` | DB + event bus readiness |
| `/api/docs` | OpenAPI docs |
| `/ws/test-floor?token=JWT` | Live telemetry WebSocket |

## Defaults on Spaces

- **SQLite** under `/data` (or `/tmp`) — no external Postgres required
- **In-process event bus** (`REDIS_URL=memory://`) — no external Redis required
- Seed users created on boot (`viewer` / `viewer123`, `admin` / `admin123`)

## Space secrets (recommended)

In **Settings → Variables and secrets**:

| Name | Example |
|------|---------|
| `JWT_SECRET` | long random string |
| `CORS_ORIGINS` | `https://your-app.vercel.app,http://localhost:3000` |
| `AUTH_DISABLED` | `false` |

Optional managed stores:

| Name | Example |
|------|---------|
| `DATABASE_URL` | Neon / Supabase Postgres URL |
| `REDIS_URL` | Upstash Redis URL (omit to keep memory bus) |

## Vercel frontend env

```
NEXT_PUBLIC_API_BASE_URL=https://YOUR_USER-wafer-yield-api.hf.space/api
NEXT_PUBLIC_WS_URL=wss://YOUR_USER-wafer-yield-api.hf.space/ws/test-floor
```

See `DEPLOY-HUGGINGFACE.md` in the monorepo for full steps.
