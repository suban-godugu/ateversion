# Deploy frontend to Vercel (API already on Render)

## Dashboard (easiest)

1. Open https://vercel.com/new
2. Import GitHub repo **`suban-godugu/ateversion`**
3. Configure:

| Setting | Value |
|---------|--------|
| Framework Preset | Next.js |
| Root Directory | **`frontend`** (click Edit → select `frontend`) |
| Build Command | `npm run build` |
| Install Command | `npm install` |
| Output Directory | (leave default) |

4. **Environment Variables** (Production + Preview):

| Name | Value |
|------|--------|
| `NEXT_PUBLIC_API_BASE_URL` | `/api` |
| `API_PROXY_TARGET` | `https://wafer-yield-api.onrender.com` |
| `NEXT_PUBLIC_WS_URL` | `wss://wafer-yield-api.onrender.com/ws/test-floor` |

5. Click **Deploy**

6. After deploy, copy your Vercel URL (e.g. `https://ateversion.vercel.app`)

7. On Render → `wafer-yield-api` → Environment → update:

| Name | Value |
|------|--------|
| `CORS_ORIGINS` | `https://YOUR-VERCEL-URL.vercel.app,http://localhost:3000` |

8. Save (Render redeploys) → open the Vercel URL → login `viewer` / `viewer123`

## Fix "Failed to fetch" on login

1. Wake the API first: open  
   `https://wafer-yield-api.onrender.com/api/health`  
   Wait until you see `"status":"ok"` (Render free tier can take 30–60s).
2. In Vercel → Project → **Settings → Environment Variables**, set the three vars above.
3. **Deployments → … → Redeploy** (or push a commit) so the proxy is active.
4. Retry login: `viewer` / `viewer123`

## Notes

- Free Render API may sleep; first load can take ~30–60s
- `NEXT_PUBLIC_*` vars are baked at build time — change them → Redeploy frontend
- Root Directory **must** be `frontend`, not repo root
- With `/api` + `API_PROXY_TARGET`, the browser stays same-origin (no CORS needed for REST)
