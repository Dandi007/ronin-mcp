"""Gate-approval facet (B-class irreversible operations) — retired (M3 rework).

``ronin_gate_approve`` / ``ronin_gate_reject`` are retired: they stay
registered (visible and callable in ``tools/list``) but every invocation
returns an explicit, structured ``RETIRED`` rejection. The retirement
guard runs before any auth / prod-write / ephemeral check.

Red line "零删除既有测试" is honoured: the same 7 test functions are
retained (names unchanged, bodies rewritten to assert the retirement
fact). Retirement is absolute regardless of prod-write / ephemeral flags.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

_COMMON: dict[str, Any] = {
    "development_id": "gd:gate-dev",
    "gate_id": "gate-1",
    "idempotency_key": "ik-gate-1",
    "expected_revision": 1,
    "operator_identity": "gd:operator",
}


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
def test_gate_approve_rejected_without_prod_write(
    mcp_server_factory: Any, make_config: Any
) -> None:
    """ronin_gate_approve is retired: it returns RETIRED (was auth reject)."""
    server = mcp_server_factory(make_config())
    _assert_retired(server, "ronin_gate_approve", dict(_COMMON))


@pytest.mark.timeout(30)
def test_gate_reject_rejected_without_prod_write(
    mcp_server_factory: Any, make_config: Any
) -> None:
    """ronin_gate_reject is retired: it returns RETIRED (was auth reject)."""
    server = mcp_server_factory(make_config())
    _assert_retired(server, "ronin_gate_reject", dict(_COMMON))


@pytest.mark.timeout(30)
def test_gate_approve_with_prod_write(
    mcp_server_factory: Any, make_config: Any
) -> None:
    """ronin_gate_approve is retired even with prod write (was approve)."""
    server = mcp_server_factory(make_config(prod_write=True))
    _assert_retired(server, "ronin_gate_approve", dict(_COMMON))


@pytest.mark.timeout(30)
def test_gate_reject_with_prod_write(
    mcp_server_factory: Any, make_config: Any
) -> None:
    """ronin_gate_reject is retired even with prod write (was reject)."""
    server = mcp_server_factory(make_config(prod_write=True))
    _assert_retired(server, "ronin_gate_reject", dict(_COMMON))


@pytest.mark.timeout(30)
def test_gate_approve_ephemeral_unlocks(
    mcp_server_factory: Any, make_config: Any
) -> None:
    """ronin_gate_approve is retired even in ephemeral mode (was ephemeral unlock)."""
    server = mcp_server_factory(make_config(ephemeral=True))
    _assert_retired(server, "ronin_gate_approve", dict(_COMMON))


@pytest.mark.timeout(30)
def test_gate_approve_ephemeral_with_prod_write(
    mcp_server_factory: Any, make_config: Any
) -> None:
    """ronin_gate_approve is retired even in ephemeral + prod write mode."""
    server = mcp_server_factory(make_config(ephemeral=True, prod_write=True))
    _assert_retired(server, "ronin_gate_approve", dict(_COMMON))


@pytest.mark.timeout(30)
def test_gate_approve_forwards_operator_identity(
    mcp_server_factory: Any, make_config: Any, controller_double: Any
) -> None:
    """ronin_gate_approve is retired: no operator_identity is forwarded.

    The retirement guard runs before any backend forwarding, so the
    Controller double must never receive a gate command for this call.
    """
    server = mcp_server_factory(make_config(prod_write=True))
    _assert_retired(server, "ronin_gate_approve", dict(_COMMON))
    gate_events = [
        e
        for events in controller_double.store["events"].values()
        for e in events
        if e["command"] == "gate"
    ]
    assert gate_events == []