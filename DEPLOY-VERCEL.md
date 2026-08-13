# Deploy: Vercel (frontend) + Render/Railway (backend)

Split hosting is required because **Vercel cannot host long-lived WebSockets**.

```
Vercel (Next.js UI)
        │  HTTPS / WSS
        ▼
Render or Railway (FastAPI + Postgres + Redis + WebSocket)
```

---

## A. Backend on Render (recommended)

1. Push this repo to GitHub.
2. Go to [render.com](https://render.com) → **New** → **Blueprint**.
3. Select the repo (uses `render.yaml`).
4. After services create, open **wafer-yield-api** → Environment:
   - Set `CORS_ORIGINS` to your Vercel URL, e.g.  
     `https://your-app.vercel.app,http://localhost:3000`
5. Wait until the API is live. Note the URL, e.g. `https://wafer-yield-api.onrender.com`.
6. Health check: `https://YOUR-API.onrender.com/api/health`
7. Seed data once (Render Shell on the API service):

```bash
python -m app.ingestion.seed
```

### Alternative: Railway

1. New project from GitHub.
2. Add **PostgreSQL** + **Redis**.
3. Deploy service with Dockerfile `backend/Dockerfile`.
4. Variables:

| Key | Value |
|-----|--------|
| `DATABASE_URL` | Railway Postgres URL (auto-normalized to asyncpg) |
| `REDIS_URL` | Railway Redis URL |
| `JWT_SECRET` | long random string |
| `CORS_ORIGINS` | `https://your-app.vercel.app` |
| `AUTH_DISABLED` | `false` |

---

## B. Frontend on Vercel

1. Go to [vercel.com](https://vercel.com) → **Add New Project** → import this GitHub repo.
2. Configure:

| Setting | Value |
|---------|--------|
| Root Directory | `frontend` |
| Framework | Next.js |
| Build Command | `npm run build` |
| Install Command | `npm install` |

3. Environment Variables (Production + Preview):

| Name | Example |
|------|---------|
| `NEXT_PUBLIC_API_BASE_URL` | `https://YOUR-API.onrender.com/api` |
| `NEXT_PUBLIC_WS_URL` | `wss://YOUR-API.onrender.com/ws/test-floor` |

4. Deploy. Open the Vercel URL and sign in (`viewer` / `viewer123`).

CLI option:

```powershell
cd frontend
npx vercel login
npx vercel --prod
```

(You will be prompted for env vars / can set them in the Vercel dashboard.)

---

## C. Wire them together

1. Deploy backend first → get API hostname.
2. Set Vercel `NEXT_PUBLIC_*` to that hostname (`https` + `wss`).
3. Set backend `CORS_ORIGINS` to the Vercel hostname.
4. Redeploy frontend if env vars changed after first build (`NEXT_PUBLIC_*` are bake-time).

---

## Checklist

- [ ] API `/api/health` returns ok
- [ ] API `/api/ready` shows database + redis true
- [ ] Vercel UI loads login
- [ ] Login works (JWT)
- [ ] Live Connection shows LIVE (WebSocket)
- [ ] Event log receives live events
- [ ] CORS not blocking browser requests

---

## Notes

- Free Render web services **sleep when idle**; first request / WS may take ~30–60s to wake.
- Do **not** run `simulation.floor_sim` in production.
- Change default seed passwords before real fab use.
- For a custom domain: point Vercel domain + update `CORS_ORIGINS` and `NEXT_PUBLIC_*`.
