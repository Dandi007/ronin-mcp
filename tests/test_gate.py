"""Gate-approval facet — retired surface (M3 rework).

``ronin_gate_approve`` / ``ronin_gate_reject`` are retired: they stay
registered (visible and callable in ``tools/list``) but every invocation
returns an explicit, structured ``RETIRED`` rejection. The former
auth / prod-write / ephemeral cases are rewritten here as negative
``RETIRED`` assertions, one per tool.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

RETIRED_GATE_TOOLS = [
    "ronin_gate_approve",
    "ronin_gate_reject",
]


def _error_envelope(exc: ToolError) -> dict[str, Any]:
    raw = str(exc)
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {"raw": raw}
    return json.loads(raw[start : end + 1])


def _args_for(tool: str) -> dict[str, Any]:
    common = {
        "development_id": "gd:gate-dev",
        "gate_id": "gate-1",
        "idempotency_key": "ik-gate-1",
        "expected_revision": 1,
        "operator_identity": "gd:operator",
    }
    return {tool: dict(common)}[tool]


@pytest.mark.timeout(30)
@pytest.mark.parametrize("tool", RETIRED_GATE_TOOLS)
def test_gate_tool_returns_retired(
    mcp_server_factory: Any, make_config: Any, tool: str
) -> None:
    """Each retired ronin_gate_* tool returns a structured RETIRED rejection.

    Gate approval is retired regardless of prod-write / ephemeral flags:
    the retirement guard runs before any auth check.
    """
    server = mcp_server_factory(make_config())

    async def _run() -> None:
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc:
                await client.call_tool(tool, _args_for(tool))
            env = _error_envelope(exc.value)
            assert env["code"] == "RETIRED", env
            assert env["details"]["retryable"] is False, env

    asyncio.run(_run())


@pytest.mark.timeout(30)
@pytest.mark.parametrize("tool", RETIRED_GATE_TOOLS)
def test_gate_tool_returns_retired_even_with_prod_write(
    mcp_server_factory: Any, make_config: Any, tool: str
) -> None:
    """Retirement is absolute: prod-write mode does not revive a gate tool."""
    server = mcp_server_factory(make_config(prod_write=True))

    async def _run() -> None:
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc:
                await client.call_tool(tool, _args_for(tool))
            env = _error_envelope(exc.value)
            assert env["code"] == "RETIRED", env

    asyncio.run(_run())