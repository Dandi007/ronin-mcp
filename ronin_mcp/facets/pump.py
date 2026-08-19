"""Pump-state facet (read-only /data/ronin/runs/)."""

from __future__ import annotations

from typing import Any

from ronin_mcp.backends.pump_state import PumpStateClient


def register(
    mcp: Any,
    pump: PumpStateClient,
    error_wrapper: Any,
) -> None:
    """Register ronin_pump_* tools on the FastMCP server."""

    @mcp.tool()
    def ronin_pump_list(limit: int = 50, status: str | None = None) -> dict[str, Any]:
        """List pump runs newest-first."""
        return error_wrapper(lambda: pump.list_runs(limit=limit, status=status))

    @mcp.tool()
    def ronin_pump_get(run_id: str) -> dict[str, Any]:
        """Get a pump run's merged state (run.json + terminal.json)."""
        return error_wrapper(lambda: pump.get_run(run_id))

    @mcp.tool()
    def ronin_pump_rounds(
        run_id: str,
        after_round: int | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Read rounds.jsonl incrementally."""
        return error_wrapper(
            lambda: pump.get_rounds(run_id, after_round=after_round, limit=limit)
        )
