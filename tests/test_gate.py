"""Gate-approval facet (spec §面 7).

ronin_gate_approve / ronin_gate_reject ALWAYS require
RONIN_PROD_WRITE=1, even for gd:-prefixed developments, because gate
approvals are B-class irreversible operations.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError


def _extract_text(result: Any) -> str:
    if hasattr(result, "content") and result.content:
        return result.content[0].text
    if hasattr(result, "text"):
        return result.text
    return str(result)


def _call(server: Any, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        async with Client(server) as client:
            result = await client.call_tool(tool, args)
            return json.loads(_extract_text(result))
    return asyncio.run(_run())


def _create_dev(server: Any, name: str = "gd:gate-dev") -> dict[str, Any]:
    return _call(server, "ronin_dev_create", {
        "name": name,
        "goal": "gate test",
        "idempotency_key": f"ik-{name}",
        "reason": "testing gate",
        "initial_handoff": {},
    })


@pytest.mark.timeout(30)
def test_gate_approve_rejected_without_prod_write(mcp_server_factory: Any, make_config: Any) -> None:
    """Gate approve is rejected without prod write, even for gd: dev."""
    server = mcp_server_factory(make_config())
    _create_dev(server, "gd:gate-reject")

    async def _run() -> None:
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc:
                await client.call_tool("ronin_gate_approve", {
                    "development_id": "gd:gate-reject",
                    "gate_id": "gate-1",
                    "idempotency_key": "ik-gate-1",
                    "expected_revision": 1,
                    "operator_identity": "gd:operator",
                })
            assert "GATE_REQUIRES_PROD_WRITE" in str(exc.value)

    asyncio.run(_run())


@pytest.mark.timeout(30)
def test_gate_reject_rejected_without_prod_write(mcp_server_factory: Any, make_config: Any) -> None:
    """Gate reject is rejected without prod write, even for gd: dev."""
    server = mcp_server_factory(make_config())
    _create_dev(server, "gd:gate-reject-r")

    async def _run() -> None:
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc:
                await client.call_tool("ronin_gate_reject", {
                    "development_id": "gd:gate-reject-r",
                    "gate_id": "gate-2",
                    "idempotency_key": "ik-gate-2",
                    "expected_revision": 1,
                    "operator_identity": "gd:operator",
                })
            assert "GATE_REQUIRES_PROD_WRITE" in str(exc.value)

    asyncio.run(_run())


@pytest.mark.timeout(30)
def test_gate_approve_with_prod_write(mcp_server_factory: Any, make_config: Any) -> None:
    """Gate approve succeeds with prod write."""
    server = mcp_server_factory(make_config(prod_write=True))
    _create_dev(server, "gd:gate-approve")
    data = _call(server, "ronin_gate_approve", {
        "development_id": "gd:gate-approve",
        "gate_id": "gate-3",
        "idempotency_key": "ik-gate-3",
        "expected_revision": 1,
        "operator_identity": "gd:operator",
    })
    assert data["state"] == "GATE_APPROVED"


@pytest.mark.timeout(30)
def test_gate_reject_with_prod_write(mcp_server_factory: Any, make_config: Any) -> None:
    """Gate reject succeeds with prod write."""
    server = mcp_server_factory(make_config(prod_write=True))
    _create_dev(server, "gd:gate-reject-ok")
    data = _call(server, "ronin_gate_reject", {
        "development_id": "gd:gate-reject-ok",
        "gate_id": "gate-4",
        "idempotency_key": "ik-gate-4",
        "expected_revision": 1,
        "operator_identity": "gd:operator",
    })
    assert data["state"] == "GATE_REJECTED"


@pytest.mark.timeout(30)
def test_gate_approve_ephemeral_unlocks(mcp_server_factory: Any, make_config: Any) -> None:
    """Ephemeral mode (priority 1) unlocks gate approvals too.

    The spec lists the guardrail rules by priority; ephemeral is rule 1
    ("无任何限制，全写面开放") and takes precedence over rule 4 (gate
    always requires prod write). This is the safest interpretation:
    ephemeral backends are disposable, so an approved gate there is
    harmless.
    """
    server = mcp_server_factory(make_config(ephemeral=True))
    _create_dev(server, "gd:gate-ephemeral")
    data = _call(server, "ronin_gate_approve", {
        "development_id": "gd:gate-ephemeral",
        "gate_id": "gate-5",
        "idempotency_key": "ik-gate-5",
        "expected_revision": 1,
        "operator_identity": "gd:operator",
    })
    assert data["state"] == "GATE_APPROVED"


@pytest.mark.timeout(30)
def test_gate_approve_ephemeral_with_prod_write(mcp_server_factory: Any, make_config: Any) -> None:
    """Gate approve succeeds in ephemeral + prod write mode."""
    server = mcp_server_factory(make_config(ephemeral=True, prod_write=True))
    _create_dev(server, "gd:gate-both")
    data = _call(server, "ronin_gate_approve", {
        "development_id": "gd:gate-both",
        "gate_id": "gate-6",
        "idempotency_key": "ik-gate-6",
        "expected_revision": 1,
        "operator_identity": "gd:operator",
    })
    assert data["state"] == "GATE_APPROVED"


@pytest.mark.timeout(30)
def test_gate_approve_forwards_operator_identity(mcp_server_factory: Any, make_config: Any, controller_double: Any) -> None:
    """The operator_identity is forwarded as X-Operator-Identity."""
    server = mcp_server_factory(make_config(prod_write=True))
    _create_dev(server, "gd:gate-fwd")
    _call(server, "ronin_gate_approve", {
        "development_id": "gd:gate-fwd",
        "gate_id": "gate-7",
        "idempotency_key": "ik-gate-7",
        "expected_revision": 1,
        "operator_identity": "gd:operator-fwd",
    })
    events = controller_double.store["events"]["gd:gate-fwd"]
    gate_events = [e for e in events if e["command"] == "gate"]
    assert len(gate_events) == 1
    assert gate_events[0]["operator_identity"] == "gd:operator-fwd"
