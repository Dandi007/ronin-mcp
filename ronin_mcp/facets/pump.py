"""Pump-state facet (read-only /data/ronin/runs/) — retired.

The pump state tools stay registered (visible and callable in
``tools/list``) but every invocation is refused with a structured
``RETIRED`` rejection (see ``ronin_mcp.disposition``). Pump run state is
no longer owned by ronin-mcp; dropping the tools would surface
``Unknown tool`` and keeping the filesystem path would surface it as an
operational fault, so the entrance returns ``RETIRED`` instead.
"""

from __future__ import annotations

from typing import Any

from ronin_mcp.backends.pump_state import PumpStateClient
from ronin_mcp.disposition import retire


def register(
    mcp: Any,
    pump: PumpStateClient,
    error_wrapper: Any,
) -> None:
    """Register the (retired) ronin_pump_* tools on the FastMCP server."""

    @mcp.tool()
    def ronin_pump_list(limit: int = 50, status: str | None = None) -> dict[str, Any]:
        """List pump runs newest-first — retired."""
        return error_wrapper(lambda: retire("ronin_pump_list"))

    @mcp.tool()
    def ronin_pump_get(run_id: str) -> dict[str, Any]:
        """Get a pump run's merged state (run.json + terminal.json) — retired."""
        return error_wrapper(lambda: retire("ronin_pump_get"))

    @mcp.tool()
    def ronin_pump_rounds(
        run_id: str,
        after_round: int | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Read rounds.jsonl incrementally — retired."""
        return error_wrapper(lambda: retire("ronin_pump_rounds"))