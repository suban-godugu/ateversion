# Deployment — Wafer Yield Intelligence

Full-stack production layout:

```
Browser
  ↓
nginx :80
  ├─ /        → frontend (Next.js)
  ├─ /api/    → FastAPI
  └─ /ws/     → FastAPI WebSocket
       ↓
 PostgreSQL + Redis
```

## Prerequisites

1. Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows)
2. Start Docker Desktop and wait until it is running
3. Open PowerShell in the repo root: `c:\ate frondend`

## 1. Create secrets

```powershell
copy .env.deploy.example .env.deploy
notepad .env.deploy
```

Set at least:

- `POSTGRES_PASSWORD` — strong DB password
- `JWT_SECRET` — long random string (32+ chars)

## 2. Build and start

```powershell
docker compose --env-file .env.deploy up -d --build
```

## 3. Seed reference floor data (first deploy)

```powershell
docker compose --env-file .env.deploy exec api python -m app.ingestion.seed
```

## 4. Open the app

- UI: http://localhost
- API docs: http://localhost/api/docs (if exposed via proxy path) or use container:
  ```powershell
  docker compose --env-file .env.deploy exec api curl -s http://127.0.0.1:8000/api/health
  ```
- Health: http://localhost/api/health
- Ready: http://localhost/api/ready

Demo login: `viewer` / `viewer123` (or `admin` / `admin123`)

## Useful commands

```powershell
# Status
docker compose --env-file .env.deploy ps

# Logs
docker compose --env-file .env.deploy logs -f api
docker compose --env-file .env.deploy logs -f frontend

# Stop
docker compose --env-file .env.deploy down

# Stop + wipe database volumes (destructive)
docker compose --env-file .env.deploy down -v
```

## Production checklist

- [ ] Change all default passwords / JWT secret
- [ ] Put HTTPS in front (Cloudflare, Traefik, or nginx TLS)
- [ ] Restrict CORS to your real domain in `.env.deploy`
- [ ] Keep `AUTH_DISABLED=false`
- [ ] Do **not** run `simulation.floor_sim` in production
- [ ] Back up the `wafer_pg` volume regularly
- [ ] Monitor `/api/ready` (DB + Redis)

## Deploy to a VPS

1. Copy this repo to the server
2. Install Docker Engine + Compose plugin
3. Create `.env.deploy` with production secrets and your public URL in `CORS_ORIGINS`
4. Run the same `docker compose ... up -d --build` commands
5. Point DNS A-record to the server and terminate TLS with nginx/Caddy/Cloudflare

## Without Docker (manual)

Not recommended for production, but for a single Windows host:

1. Run PostgreSQL + Redis
2. Backend: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
3. Frontend: `npm run build && npm run start`
4. Set `NEXT_PUBLIC_API_BASE_URL` / `NEXT_PUBLIC_WS_URL` to your public API host
