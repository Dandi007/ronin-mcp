"""Shared fixtures for Ronin MCP tests.

Spins up an ephemeral agent-bus ``BusServer`` in-process (db + http on a
free port) so the ronin-mcp gateway can be exercised end-to-end over real
HTTP. Also provides a fake bus client for pure logic tests, and a tmp pump
runs root.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import time
from collections.abc import Generator
from typing import Any

import pytest


# Candidate locations for the agent-bus source tree. If any is present we
# add it to sys.path so the round-trip fixtures can import agent_bus. This
# keeps the dev dependency optional: tests skip gracefully when agent-bus is
# not reachable on the filesystem.
_AGENT_BUS_CANDIDATES = [
    "/data/code/self/agent-bus",
    os.path.join(os.path.dirname(__file__), "..", "..", "agent-bus"),
]


def _ensure_agent_bus() -> bool:
    try:
        import agent_bus  # noqa: F401
        return True
    except ImportError:
        pass
    for candidate in _AGENT_BUS_CANDIDATES:
        cand = os.path.abspath(candidate)
        if os.path.isfile(os.path.join(cand, "agent_bus", "__init__.py")):
            if cand not in sys.path:
                sys.path.insert(0, cand)
            try:
                import agent_bus  # noqa: F401
                return True
            except ImportError:
                continue
    return False


_HAS_AGENT_BUS = _ensure_agent_bus()


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def gateway_token() -> str:
    return "ronin-test-gateway-token-32-chars!"


@pytest.fixture
def admin_token() -> str:
    return "ronin-test-admin-token-32-chars!!"


@pytest.fixture
def bus_env(
    gateway_token: str,
    admin_token: str,
) -> Generator[dict[str, Any], None, None]:
    """A live ephemeral agent-bus HTTP server on a free port."""
    try:
        from agent_bus.bus import Bus
        from agent_bus.config import DEFAULT_CONFIG, _deep_merge
        from agent_bus.db import Database
        from agent_bus.http_server import BusServer
    except ImportError:
        pytest.skip("agent-bus not installed")
    tmp = tempfile.mkdtemp(prefix="ronin-bus-")
    db_path = os.path.join(tmp, "bus.sqlite3")
    config = _deep_merge(DEFAULT_CONFIG, {"server": {"port": 0}})
    config["server"]["host"] = "127.0.0.1"
    config["server"]["port"] = _free_port()
    config["runtime_root"] = tmp

    db = Database(db_path)
    db.migrate()
    db._bootstrap_admin(admin_token)
    db._bootstrap_gateway(gateway_token)
    db._seed_builtin_protocol()
    db._seed_chat_protocol()
    db._seed_agent_msg_protocol()
    db._seed_inbox_channels()

    bus = Bus(db)
    server = BusServer(config, db, bus)
    server.start()
    time.sleep(0.2)
    host, port = server.bound_address or ("127.0.0.1", config["server"]["port"])
    url = f"http://{host}:{port}"

    yield {
        "url": url,
        "gateway_token": gateway_token,
        "admin_token": admin_token,
        "db": db,
        "server": server,
        "tmp": tmp,
    }

    server.stop()
    time.sleep(0.1)


@pytest.fixture
def bus_client(bus_env: dict[str, Any]):
    """A real AgentBusClient pointed at the ephemeral bus."""
    from ronin_mcp.backends.agent_bus import AgentBusClient

    client = AgentBusClient(bus_env["url"], bus_env["gateway_token"])
    yield client
    client.close()


class FakeBusClient:
    """Records calls and returns canned responses for pure logic tests."""

    def __init__(self, *, response: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, str, dict[str, Any], str | None]] = []
        self._response = response or {"ok": True}

    def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(("GET", path, params or {}, as_agent_id))
        return dict(self._response)

    def post(
        self,
        path: str,
        body: dict[str, Any],
        *,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(("POST", path, body, as_agent_id))
        return dict(self._response)

    def delete(
        self,
        path: str,
        *,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(("DELETE", path, {}, as_agent_id))
        return dict(self._response)


class FakeControllerClient:
    def __init__(self, *, response: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, str, dict[str, Any], str | None]] = []
        self._response = response or {"ok": True}

    def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        operator_identity: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(("GET", path, params or {}, operator_identity))
        return dict(self._response)

    def post(
        self,
        path: str,
        body: dict[str, Any],
        *,
        operator_identity: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(("POST", path, body, operator_identity))
        return dict(self._response)


class FakeWorkFolderClient:
    def __init__(self, *, response: dict[str, Any] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._response = response or {"ok": True}

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((name, arguments))
        return dict(self._response)


@pytest.fixture
def fake_bus() -> FakeBusClient:
    return FakeBusClient()


@pytest.fixture
def fake_controller() -> FakeControllerClient:
    return FakeControllerClient()


@pytest.fixture
def fake_wf() -> FakeWorkFolderClient:
    return FakeWorkFolderClient()


def _make_server(
    *,
    bus: Any | None = None,
    controller: Any | None = None,
    wf: Any | None = None,
    pump: Any | None = None,
    auth_state: dict[str, Any] | None = None,
) -> Any:
    from ronin_mcp.server import build_mcp_server

    config: dict[str, Any] = {"backends": {}}
    if auth_state is None:
        auth_state = {"ephemeral": False, "prod_write_enabled": False}
    return build_mcp_server(
        config,
        auth_state=auth_state,
        bus_client=bus,
        controller_client=controller,
        work_folder_client=wf,
        pump_client=pump,
    )


@pytest.fixture
def mcp_with_fakes(
    fake_bus: FakeBusClient,
    fake_controller: FakeControllerClient,
    fake_wf: FakeWorkFolderClient,
) -> Any:
    return _make_server(
        bus=fake_bus,
        controller=fake_controller,
        wf=fake_wf,
        auth_state={"ephemeral": False, "prod_write_enabled": False},
    )


@pytest.fixture
def mcp_prod(
    fake_bus: FakeBusClient,
    fake_controller: FakeControllerClient,
    fake_wf: FakeWorkFolderClient,
) -> Any:
    return _make_server(
        bus=fake_bus,
        controller=fake_controller,
        wf=fake_wf,
        auth_state={"ephemeral": False, "prod_write_enabled": True},
    )


@pytest.fixture
def mcp_ephemeral(
    fake_bus: FakeBusClient,
    fake_controller: FakeControllerClient,
    fake_wf: FakeWorkFolderClient,
) -> Any:
    return _make_server(
        bus=fake_bus,
        controller=fake_controller,
        wf=fake_wf,
        auth_state={"ephemeral": True, "prod_write_enabled": False},
    )


@pytest.fixture
def pump_root(tmp_path) -> Generator[tuple[str, str], None, None]:
    """A tmp runs root with two pump runs."""
    root = tmp_path / "runs"
    root.mkdir()

    run1 = root / "run-aaa"
    run1.mkdir()
    (run1 / "run.json").write_text(json.dumps({
        "run_id": "run-aaa",
        "folder_id": "wf-1",
        "status": "running",
        "started_at": "2026-08-19T10:00:00Z",
        "rounds": 3,
        "route_attempts": 2,
    }))
    (run1 / "rounds.jsonl").write_text(
        json.dumps({"round": 1, "event": "tick"}) + "\n"
        + json.dumps({"round": 2, "event": "tick"}) + "\n"
        + json.dumps({"round": 3, "event": "done"}) + "\n"
    )

    run2 = root / "run-bbb"
    run2.mkdir()
    (run2 / "run.json").write_text(json.dumps({
        "run_id": "run-bbb",
        "folder_id": "wf-2",
        "status": "terminal",
        "started_at": "2026-08-19T11:00:00Z",
        "terminal_at": "2026-08-19T12:00:00Z",
        "rounds": 1,
        "route_attempts": 1,
    }))
    (run2 / "terminal.json").write_text(json.dumps({"reason": "complete", "exit_code": 0}))

    yield str(root), "run-aaa"
