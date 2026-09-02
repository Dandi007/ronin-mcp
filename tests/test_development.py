"""Development (dd dispatch) facet — retired surface (M3 rework).

The ``ronin_dev_*`` tools are retired: they stay registered (visible and
callable in ``tools/list``) but every invocation must return an
explicit, structured ``RETIRED`` rejection instead of surfacing as
``Unknown tool`` or a backend fault. The former positive / auth cases are
rewritten here as negative ``RETIRED`` assertions, one per tool.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from ronin_mcp.disposition import DISPOSITIONS, RETIRED

RETIRED_DEV_TOOLS = [
    "ronin_dev_list",
    "ronin_dev_get",
    "ronin_dev_events",
    "ronin_dev_evidence",
    "ronin_dev_create",
    "ronin_dev_start",
    "ronin_dev_steer",
    "ronin_dev_reconfigure",
    "ronin_dev_control",
    "ronin_dev_relock",
]


def _error_envelope(exc: ToolError) -> dict[str, Any]:
    """Parse the structured envelope from a ToolError message."""
    raw = str(exc)
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {"raw": raw}
    return json.loads(raw[start : end + 1])


def _assert_retired(server: Any, tool: str, args: dict[str, Any]) -> None:
    async def _run() -> None:
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc:
                await client.call_tool(tool, args)
            env = _error_envelope(exc.value)
            assert env["code"] == "RETIRED", env
            assert env["details"]["retryable"] is False, env

    asyncio.run(_run())


def _args_for(tool: str) -> dict[str, Any]:
    common_command = {
        "development_id": "gd:test-dev",
        "idempotency_key": "ik-1",
        "expected_revision": 1,
    }
    return {
        "ronin_dev_list": {},
        "ronin_dev_get": {"development_id": "gd:test-dev"},
        "ronin_dev_events": {"development_id": "gd:test-dev"},
        "ronin_dev_evidence": {"development_id": "gd:test-dev"},
        "ronin_dev_create": {
            "name": "gd:test-dev",
            "goal": "test goal",
            "idempotency_key": "ik-1",
            "reason": "retired",
            "initial_handoff": {},
        },
        "ronin_dev_start": dict(common_command),
        "ronin_dev_steer": {**common_command, "instruction": "do X"},
        "ronin_dev_reconfigure": dict(common_command),
        "ronin_dev_control": {**common_command, "action": "pause"},
        "ronin_dev_relock": {**common_command, "plugin_commit": "abc123"},
    }[tool]


@pytest.mark.timeout(30)
@pytest.mark.parametrize("tool", RETIRED_DEV_TOOLS)
def test_dev_tool_returns_retired(
    mcp_server_factory: Any, make_config: Any, tool: str
) -> None:
    """Each retired ronin_dev_* tool returns a structured RETIRED rejection.

    If a tool is flipped back to its "available" implementation this test
    turns red (no ToolError raised, or a non-RETIRED envelope).
    """
    server = mcp_server_factory(make_config())
    _assert_retired(server, tool, _args_for(tool))


@pytest.mark.timeout(30)
def test_dev_tools_remain_registered_and_visible(
    mcp_server_factory: Any, make_config: Any
) -> None:
    """All 15 retired tools (dev/gate/pump) stay visible in tools/list."""
    server = mcp_server_factory(make_config())

    async def _run() -> None:
        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            for name in DISPOSITIONS:
                assert name in names, f"{name} missing from tools/list"
            for name in RETIRED_DEV_TOOLS:
                assert DISPOSITIONS[name]["disposition"] == RETIRED

    asyncio.run(_run())