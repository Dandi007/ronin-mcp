"""Facet 6: Pump state (ronin_pump_*)."""

from __future__ import annotations

from typing import Any

from ronin_mcp.backends.agent_bus import _BackendError
from ronin_mcp.backends.pump_state import PumpStateClient


def register(mcp: Any, *, pump: PumpStateClient) -> None:
    @mcp.tool()
    def ronin_pump_list(limit: int = 50, status: str | None = None) -> dict[str, Any]:
        """List pump runs."""
        try:
            return pump.list_runs(limit=limit, status=status)
        except _BackendError as exc:
            return exc.as_error_dict()

    @mcp.tool()
    def ronin_pump_get(run_id: str) -> dict[str, Any]:
        """Get run state (run.json + terminal.json)."""
        try:
            return pump.get_run(run_id)
        except _BackendError as exc:
            return exc.as_error_dict()

    @mcp.tool()
    def ronin_pump_rounds(
        run_id: str,
        after_round: int | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Get pump round events (rounds.jsonl)."""
        try:
            return pump.list_rounds(run_id, after_round=after_round, limit=limit)
        except _BackendError as exc:
            return exc.as_error_dict()
