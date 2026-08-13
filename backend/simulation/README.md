# Development simulation (non-production)

This package is a **development-only** floor simulator.

It must **never** be imported by production FastAPI services under `app/`.

Production path:

```
ATE/STDF → parser → ingestion → PostgreSQL → AI → Redis → WebSocket → React
```

Simulation path (local/dev only):

```
python -m simulation.floor_sim
  → POST /api/telemetry/events (authenticated)
  → same production ingest pipeline
```

Do not present simulated data as live fab telemetry outside of local engineering environments.
