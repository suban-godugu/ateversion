# Backend on Render — step by step

Your API (FastAPI + Postgres + Redis + WebSocket) deploys from `render.yaml`.

## 0. Push this project to GitHub (required)

This folder is **not a git repo yet**. Do this once:

```powershell
cd "c:\ate frondend"
git init
git add .
git commit -m "Initial Wafer Yield Intelligence platform"
```

Create a GitHub repo, then:

```powershell
gh repo create wafer-yield-intelligence --private --source=. --remote=origin --push
```

Or create the repo on github.com and:

```powershell
git remote add origin https://github.com/YOUR_USER/wafer-yield-intelligence.git
git branch -M main
git push -u origin main
```

---

## 1. Create Blueprint on Render

1. Open https://dashboard.render.com  
2. Sign in with GitHub  
3. **New +** → **Blueprint**  
4. Select `wafer-yield-intelligence` (or your repo name)  
5. Render reads `render.yaml` and proposes:
   - `wafer-yield-api` (web)
   - `wafer-yield-db` (Postgres)
   - `wafer-yield-redis` (Key Value / Redis)
6. Click **Apply**

Wait until the API status is **Live** (first build can take several minutes).

---

## 2. Verify API

Open:

```
https://wafer-yield-api.onrender.com/api/health
```

(Use the exact URL shown on the service page.)

Expect:

```json
{"status":"ok","database":true,"redis":true,"app":"Wafer Yield Intelligence API"}
```

Also check:

```
https://YOUR-API.onrender.com/api/ready
```

---

## 3. Seed floor data (once)

1. Render dashboard → `wafer-yield-api` → **Shell**  
2. Run:

```bash
python -m app.ingestion.seed
```

Demo users are created on startup (`viewer` / `viewer123`, `admin` / `admin123`, …).

---

## 4. CORS (before Vercel frontend)

When you have a Vercel URL, set on `wafer-yield-api` → **Environment**:

| Key | Value |
|-----|--------|
| `CORS_ORIGINS` | `https://your-app.vercel.app,http://localhost:3000` |

Save → service redeploys.

---

## 5. Give these URLs to Vercel later

| Vercel env | Value |
|------------|--------|
| `NEXT_PUBLIC_API_BASE_URL` | `https://YOUR-API.onrender.com/api` |
| `NEXT_PUBLIC_WS_URL` | `wss://YOUR-API.onrender.com/ws/test-floor` |

---

## Notes

- Free web services **sleep after idle**; first request may take 30–60s.
- Free Key Value / Postgres plans may require a Render account with billing method on file (still free tier).
- If Blueprint fails on `keyvalue`, create a **Redis** instance manually and paste `REDIS_URL` into the API env.
- Do not run `simulation.floor_sim` on Render.

## Manual deploy (without Blueprint)

If Blueprint is unavailable:

1. **New → PostgreSQL** → copy External Database URL  
2. **New → Key Value** (Redis) → copy connection string  
3. **New → Web Service** → Docker  
   - Root directory: repo root  
   - Dockerfile path: `backend/Dockerfile`  
   - Docker context: `backend`  
4. Add env vars: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`, `CORS_ORIGINS`, `AUTH_DISABLED=false`
