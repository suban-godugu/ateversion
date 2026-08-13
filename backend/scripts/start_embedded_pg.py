"""Start an embedded PostgreSQL on port 55432 for local development."""

from __future__ import annotations

from pathlib import Path

from pg0 import Pg0

DATA = Path(__file__).resolve().parents[1] / ".pgdata"


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    pg = Pg0(
        name="wafer_yield",
        port=55432,
        username="wafer_yield",
        password="wafer_yield",
        database="wafer_yield",
        data_dir=str(DATA),
    )
    info = pg.start()
    print(info)
    print("DATABASE_URL=postgresql+asyncpg://wafer_yield:wafer_yield@127.0.0.1:55432/wafer_yield")
    print("Embedded Postgres running. Keep this process alive.")
    try:
        import time

        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pg.stop()


if __name__ == "__main__":
    main()
