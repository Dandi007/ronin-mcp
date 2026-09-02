"""Pump-state facet — retired surface (M3 rework).

``ronin_pump_*`` tools are retired: they stay registered (visible and
callable in ``tools/list``) but every invocation returns an explicit,
structured ``RETIRED`` rejection. The former filesystem-backed cases are
rewritten here as negative ``RETIRED`` assertions, one per tool.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

RETIRED_PUMP_TOOLS = [
    "ronin_pump_list",
    "ronin_pump_get",
    "ronin_pump_rounds",
]


def _error_envelope(exc: ToolError) -> dict[str, Any]:
    raw = str(exc)
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {"raw": raw}
    return json.loads(raw[start : end + 1])


def _args_for(tool: str) -> dict[str, Any]:
    return {
        "ronin_pump_list": {},
        "ronin_pump_get": {"run_id": "run-1"},
        "ronin_pump_rounds": {"run_id": "run-1"},
    }[tool]


@pytest.mark.timeout(30)
@pytest.mark.parametrize("tool", RETIRED_PUMP_TOOLS)
def test_pump_tool_returns_retired(
    mcp_server_factory: Any, make_config: Any, tool: str
) -> None:
    """Each retired ronin_pump_* tool returns a structured RETIRED rejection."""
    server = mcp_server_factory(make_config())

    async def _run() -> None:
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc:
                await client.call_tool(tool, _args_for(tool))
            env = _error_envelope(exc.value)
            assert env["code"] == "RETIRED", env
            assert env["details"]["retryable"] is False, env

    asyncio.run(_run())