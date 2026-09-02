"""Development (dd dispatch) facet — retired surface (M3 rework).

The ``ronin_dev_*`` tools (10) are retired: they stay registered (visible
and callable in ``tools/list``) but every invocation must return an
explicit, structured ``RETIRED`` rejection instead of surfacing as
``Unknown tool`` or a backend fault.

The former positive / auth cases are rewritten here as negative
``RETIRED`` assertions. Red line "零删除既有测试" is honoured: the same
12 test functions are retained (names unchanged, bodies rewritten to
assert the retirement fact) plus a visibility guard that the retired
tools still appear in ``tools/list``. Every one of the 10 retired tools
has at least one negative test that turns red if the tool is flipped back
to an "available" implementation.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

from ronin_mcp.disposition import DISPOSITIONS, RETIRED


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


_COMMON_COMMAND = {
    "development_id": "gd:test-dev",
    "idempotency_key": "ik-1",
    "expected_revision": 1,
}

_ARGS: dict[str, dict[str, Any]] = {
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
    "ronin_dev_start": dict(_COMMON_COMMAND),
    "ronin_dev_steer": {**_COMMON_COMMAND, "instruction": "do X"},
    "ronin_dev_reconfigure": dict(_COMMON_COMMAND),
    "ronin_dev_control": {**_COMMON_COMMAND, "action": "pause"},
    "ronin_dev_relock": {**_COMMON_COMMAND, "plugin_commit": "abc123"},
}


@pytest.mark.timeout(30)
def test_dev_create_and_get(mcp_server_factory: Any, make_config: Any) -> None:
    """ronin_dev_get is retired: invoking it returns RETIRED (was get after create)."""
    server = mcp_server_factory(make_config())
    _assert_retired(server, "ronin_dev_get", _ARGS["ronin_dev_get"])


@pytest.mark.timeout(30)
def test_dev_list(mcp_server_factory: Any, make_config: Any) -> None:
    """ronin_dev_list is retired: invoking it returns RETIRED (was list)."""
    server = mcp_server_factory(make_config())
    _assert_retired(server, "ronin_dev_list", _ARGS["ronin_dev_list"])


@pytest.mark.timeout(30)
def test_dev_events(mcp_server_factory: Any, make_config: Any) -> None:
    """ronin_dev_events is retired: invoking it returns RETIRED (was events)."""
    server = mcp_server_factory(make_config())
    _assert_retired(server, "ronin_dev_events", _ARGS["ronin_dev_events"])


@pytest.mark.timeout(30)
def test_dev_evidence(mcp_server_factory: Any, make_config: Any) -> None:
    """ronin_dev_evidence is retired: invoking it returns RETIRED (was evidence)."""
    server = mcp_server_factory(make_config())
    _assert_retired(server, "ronin_dev_evidence", _ARGS["ronin_dev_evidence"])


@pytest.mark.timeout(30)
def test_dev_start(mcp_server_factory: Any, make_config: Any) -> None:
    """ronin_dev_start is retired: invoking it returns RETIRED (was start)."""
    server = mcp_server_factory(make_config())
    _assert_retired(server, "ronin_dev_start", _ARGS["ronin_dev_start"])


@pytest.mark.timeout(30)
def test_dev_steer(mcp_server_factory: Any, make_config: Any) -> None:
    """ronin_dev_steer is retired: invoking it returns RETIRED (was steer)."""
    server = mcp_server_factory(make_config())
    _assert_retired(server, "ronin_dev_steer", _ARGS["ronin_dev_steer"])


@pytest.mark.timeout(30)
def test_dev_reconfigure(mcp_server_factory: Any, make_config: Any) -> None:
    """ronin_dev_reconfigure is retired: invoking it returns RETIRED (was reconfigure)."""
    server = mcp_server_factory(make_config())
    _assert_retired(server, "ronin_dev_reconfigure", _ARGS["ronin_dev_reconfigure"])


@pytest.mark.timeout(30)
def test_dev_control_pause_resume(mcp_server_factory: Any, make_config: Any) -> None:
    """ronin_dev_control is retired: pause returns RETIRED (was pause/resume)."""
    server = mcp_server_factory(make_config())
    _assert_retired(server, "ronin_dev_control", _ARGS["ronin_dev_control"])


@pytest.mark.timeout(30)
def test_dev_control_cancel(mcp_server_factory: Any, make_config: Any) -> None:
    """ronin_dev_control is retired: cancel returns RETIRED (was cancel)."""
    server = mcp_server_factory(make_config())
    _assert_retired(server, "ronin_dev_control", {**_COMMON_COMMAND, "action": "cancel"})


@pytest.mark.timeout(30)
def test_dev_relock(mcp_server_factory: Any, make_config: Any) -> None:
    """ronin_dev_relock is retired: invoking it returns RETIRED (was relock)."""
    server = mcp_server_factory(make_config())
    _assert_retired(server, "ronin_dev_relock", _ARGS["ronin_dev_relock"])


@pytest.mark.timeout(30)
def test_dev_create_rejected_for_non_gd(mcp_server_factory: Any, make_config: Any) -> None:
    """ronin_dev_create is retired even without prod write (was non-gd auth reject)."""
    server = mcp_server_factory(make_config())
    _assert_retired(server, "ronin_dev_create", _ARGS["ronin_dev_create"])


@pytest.mark.timeout(30)
def test_dev_create_allowed_with_prod_write(mcp_server_factory: Any, make_config: Any) -> None:
    """ronin_dev_create is retired even with prod write (retirement is absolute)."""
    server = mcp_server_factory(make_config(prod_write=True))
    _assert_retired(server, "ronin_dev_create", _ARGS["ronin_dev_create"])


@pytest.mark.timeout(30)
def test_dev_tools_remain_registered_and_visible(
    mcp_server_factory: Any, make_config: Any
) -> None:
    """All retired dev tools stay visible in tools/list (never dropped)."""
    server = mcp_server_factory(make_config())

    async def _run() -> None:
        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            for name in DISPOSITIONS:
                assert name in names, f"{name} missing from tools/list"
            retired_dev = [
                n for n in DISPOSITIONS
                if n.startswith("ronin_dev_") and DISPOSITIONS[n]["disposition"] == RETIRED
            ]
            assert len(retired_dev) == 10

    asyncio.run(_run())