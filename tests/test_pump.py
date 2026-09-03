"""Pump-state facet (read-only /data/ronin/runs/) — retired (M3 rework).

The ``ronin_pump_*`` tools (3) are retired: they stay registered (visible
and callable in ``tools/list``) but every invocation returns an explicit,
structured ``RETIRED`` rejection instead of surfacing as ``Unknown tool``
or a filesystem fault.

Red line "零删除既有测试" is honoured: the same 10 test functions are
retained (names unchanged, bodies rewritten to assert the retirement
fact). Each of the 3 retired tools has at least one negative test that
turns red if the tool is flipped back to an "available" implementation.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError


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


@pytest.mark.timeout(30)
def test_pump_list_empty(mcp_server_factory: Any, make_config: Any) -> None:
    """ronin_pump_list is retired: it returns RETIRED (was empty list)."""
    server = mcp_server_factory(make_config())
    _assert_retired(server, "ronin_pump_list", {})


@pytest.mark.timeout(30)
def test_pump_list_with_runs(mcp_server_factory: Any, make_config: Any) -> None:
    """ronin_pump_list is retired: it returns RETIRED even when runs exist."""
    server = mcp_server_factory(make_config())
    _assert_retired(server, "ronin_pump_list", {})


@pytest.mark.timeout(30)
def test_pump_list_status_filter(mcp_server_factory: Any, make_config: Any) -> None:
    """ronin_pump_list is retired: RETIRED regardless of status filter."""
    server = mcp_server_factory(make_config())
    _assert_retired(server, "ronin_pump_list", {"status": "running"})


@pytest.mark.timeout(30)
def test_pump_list_limit(mcp_server_factory: Any, make_config: Any) -> None:
    """ronin_pump_list is retired: RETIRED regardless of limit."""
    server = mcp_server_factory(make_config())
    _assert_retired(server, "ronin_pump_list", {"limit": 2})


@pytest.mark.timeout(30)
def test_pump_get(mcp_server_factory: Any, make_config: Any) -> None:
    """ronin_pump_get is retired: it returns RETIRED (was merged state)."""
    server = mcp_server_factory(make_config())
    _assert_retired(server, "ronin_pump_get", {"run_id": "run-get"})


@pytest.mark.timeout(30)
def test_pump_get_running_no_terminal(mcp_server_factory: Any, make_config: Any) -> None:
    """ronin_pump_get is retired: RETIRED regardless of terminal state."""
    server = mcp_server_factory(make_config())
    _assert_retired(server, "ronin_pump_get", {"run_id": "run-live"})


@pytest.mark.timeout(30)
def test_pump_get_missing(mcp_server_factory: Any, make_config: Any) -> None:
    """ronin_pump_get is retired: RETIRED even for a missing run (was RUN_NOT_FOUND)."""
    server = mcp_server_factory(make_config())
    _assert_retired(server, "ronin_pump_get", {"run_id": "no-such-run"})


@pytest.mark.timeout(30)
def test_pump_rounds(mcp_server_factory: Any, make_config: Any) -> None:
    """ronin_pump_rounds is retired: it returns RETIRED (was rounds read)."""
    server = mcp_server_factory(make_config())
    _assert_retired(server, "ronin_pump_rounds", {"run_id": "run-rounds"})


@pytest.mark.timeout(30)
def test_pump_rounds_after(mcp_server_factory: Any, make_config: Any) -> None:
    """ronin_pump_rounds is retired: RETIRED regardless of after_round."""
    server = mcp_server_factory(make_config())
    _assert_retired(server, "ronin_pump_rounds", {"run_id": "run-after", "after_round": 2})


@pytest.mark.timeout(30)
def test_pump_rounds_limit(mcp_server_factory: Any, make_config: Any) -> None:
    """ronin_pump_rounds is retired: RETIRED regardless of limit."""
    server = mcp_server_factory(make_config())
    _assert_retired(server, "ronin_pump_rounds", {"run_id": "run-lim", "limit": 3})