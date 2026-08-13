"""
DEPRECATED production entrypoint.

Continuous synthetic floor traffic belongs in `backend/simulation/` only.
Use:

    python -m simulation.floor_sim

This module intentionally does not emit simulated production metrics.
"""

from __future__ import annotations


def main() -> None:
    raise SystemExit(
        "telemetry_worker removed from production path. "
        "Run development simulation with: python -m simulation.floor_sim"
    )


if __name__ == "__main__":
    main()
