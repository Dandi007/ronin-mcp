"""Development (dd dispatch) facet (spec §面 4).

Exercises ronin_dev_list / get / events / evidence / create / start /
steer / reconfigure / control / relock against the Controller HTTP
double.
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


def _create_dev(server: Any, name: str = "gd:test-dev") -> dict[str, Any]:
    return _call(server, "ronin_dev_create", {
        "name": name,
        "goal": "test goal",
        "idempotency_key": f"ik-{name}",
        "reason": "testing",
        "initial_handoff": {"target_commit": "abc123"},
    })


@pytest.mark.timeout(30)
def test_dev_create_and_get(mcp_server_factory: Any, make_config: Any) -> None:
    """Create a development and get its state."""
    server = mcp_server_factory(make_config())
    created = _create_dev(server)
    assert created["name"] == "gd:test-dev"
    assert created["state"] == "BOOTSTRAPPING"

    fetched = _call(server, "ronin_dev_get", {"development_id": "gd:test-dev"})
    assert fetched["development_id"] == "gd:test-dev"
    assert fetched["state"] == "BOOTSTRAPPING"


@pytest.mark.timeout(30)
def test_dev_list(mcp_server_factory: Any, make_config: Any) -> None:
    """List developments."""
    server = mcp_server_factory(make_config())
    _create_dev(server, "gd:list-dev-1")
    _create_dev(server, "gd:list-dev-2")
    data = _call(server, "ronin_dev_list", {})
    devs = data["developments"]
    assert len(devs) >= 2
    names = {d["name"] for d in devs}
    assert "gd:list-dev-1" in names
    assert "gd:list-dev-2" in names


@pytest.mark.timeout(30)
def test_dev_events(mcp_server_factory: Any, make_config: Any) -> None:
    """Get development events."""
    server = mcp_server_factory(make_config())
    _create_dev(server, "gd:ev-dev")
    _call(server, "ronin_dev_start", {
        "development_id": "gd:ev-dev",
        "idempotency_key": "ik-start-1",
        "expected_revision": 1,
    })
    data = _call(server, "ronin_dev_events", {"development_id": "gd:ev-dev"})
    events = data["events"]
    assert len(events) >= 1
    assert any(e["command"] == "start" for e in events)


@pytest.mark.timeout(30)
def test_dev_evidence(mcp_server_factory: Any, make_config: Any) -> None:
    """Get development evidence chain."""
    server = mcp_server_factory(make_config())
    _create_dev(server, "gd:evidence-dev")
    data = _call(server, "ronin_dev_evidence", {"development_id": "gd:evidence-dev"})
    assert data["development_id"] == "gd:evidence-dev"


@pytest.mark.timeout(30)
def test_dev_start(mcp_server_factory: Any, make_config: Any) -> None:
    """Start a BOOTSTRAPPING development."""
    server = mcp_server_factory(make_config())
    _create_dev(server, "gd:start-dev")
    data = _call(server, "ronin_dev_start", {
        "development_id": "gd:start-dev",
        "idempotency_key": "ik-start-2",
        "expected_revision": 1,
    })
    assert data["revision"] >= 2


@pytest.mark.timeout(30)
def test_dev_steer(mcp_server_factory: Any, make_config: Any) -> None:
    """Steer a development."""
    server = mcp_server_factory(make_config())
    _create_dev(server, "gd:steer-dev")
    data = _call(server, "ronin_dev_steer", {
        "development_id": "gd:steer-dev",
        "instruction": "do X",
        "idempotency_key": "ik-steer-1",
        "expected_revision": 1,
    })
    assert data["revision"] >= 2


@pytest.mark.timeout(30)
def test_dev_reconfigure(mcp_server_factory: Any, make_config: Any) -> None:
    """Reconfigure a development."""
    server = mcp_server_factory(make_config())
    _create_dev(server, "gd:reconf-dev")
    data = _call(server, "ronin_dev_reconfigure", {
        "development_id": "gd:reconf-dev",
        "idempotency_key": "ik-reconf-1",
        "expected_revision": 1,
        "profile": "fast",
    })
    assert data["revision"] >= 2


@pytest.mark.timeout(30)
def test_dev_control_pause_resume(mcp_server_factory: Any, make_config: Any) -> None:
    """Pause and resume a development."""
    server = mcp_server_factory(make_config())
    _create_dev(server, "gd:control-dev")
    paused = _call(server, "ronin_dev_control", {
        "development_id": "gd:control-dev",
        "action": "pause",
        "idempotency_key": "ik-pause-1",
        "expected_revision": 1,
    })
    assert paused["state"] == "PAUSED"
    resumed = _call(server, "ronin_dev_control", {
        "development_id": "gd:control-dev",
        "action": "resume",
        "idempotency_key": "ik-resume-1",
        "expected_revision": paused["revision"],
    })
    assert resumed["state"] == "RUNNING"


@pytest.mark.timeout(30)
def test_dev_control_cancel(mcp_server_factory: Any, make_config: Any) -> None:
    """Cancel a development."""
    server = mcp_server_factory(make_config())
    _create_dev(server, "gd:cancel-dev")
    data = _call(server, "ronin_dev_control", {
        "development_id": "gd:cancel-dev",
        "action": "cancel",
        "idempotency_key": "ik-cancel-1",
        "expected_revision": 1,
    })
    assert data["state"] == "CANCELLED"


@pytest.mark.timeout(30)
def test_dev_relock(mcp_server_factory: Any, make_config: Any) -> None:
    """Relock a development to a new plugin commit."""
    server = mcp_server_factory(make_config())
    _create_dev(server, "gd:relock-dev")
    data = _call(server, "ronin_dev_relock", {
        "development_id": "gd:relock-dev",
        "plugin_commit": "def456",
        "idempotency_key": "ik-relock-1",
        "expected_revision": 1,
    })
    assert data["revision"] >= 2


@pytest.mark.timeout(30)
def test_dev_create_rejected_for_non_gd(mcp_server_factory: Any, make_config: Any) -> None:
    """Non-gd: dev_create is rejected without prod write."""
    server = mcp_server_factory(make_config())

    async def _run() -> None:
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc:
                await client.call_tool("ronin_dev_create", {
                    "name": "prod-dev",
                    "goal": "prod",
                    "idempotency_key": "ik-prod-dev",
                    "reason": "prod",
                    "initial_handoff": {},
                })
            assert "PROD_WRITE_NOT_AUTHORIZED" in str(exc.value)

    asyncio.run(_run())


@pytest.mark.timeout(30)
def test_dev_create_allowed_with_prod_write(mcp_server_factory: Any, make_config: Any) -> None:
    """Non-gd: dev_create succeeds with prod write."""
    server = mcp_server_factory(make_config(prod_write=True))
    data = _call(server, "ronin_dev_create", {
        "name": "prod-dev-ok",
        "goal": "prod",
        "idempotency_key": "ik-prod-ok",
        "reason": "prod",
        "initial_handoff": {},
    })
    assert data["name"] == "prod-dev-ok"
