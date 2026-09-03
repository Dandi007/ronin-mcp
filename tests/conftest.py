"""Test fixtures for Ronin MCP.

Provides an ephemeral bus + tmp dir harness:
- agent-bus HTTP double on an OS-assigned port (real TCP)
- a fake work-folder MCP client that records calls and returns canned
  responses (no real katana-work-folder process needed)
- a tmp directory the ephemeral work-folder backend writes into

The fixtures build a FastMCP server with the doubles injected as
backend clients, then expose an in-memory FastMCP Client so tests can
call tools without crossing the network for the MCP leg.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from collections.abc import Generator
from typing import Any

import pytest

# Ensure the package is importable when running with `uv run --extra dev python -m pytest`
# from the repo root. hatchling installs the package in dev mode, but a
# bare `python -m pytest` invocation may not have it on sys.path.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def tmp_runs_root() -> Generator[str, None, None]:
    with tempfile.TemporaryDirectory(prefix="ronin-ephemeral-") as path:
        yield path


@pytest.fixture
def bus_double() -> Generator[Any, None, None]:
    from tests.doubles import make_bus_double

    server = make_bus_double()
    server.start()
    try:
        yield server
    finally:
        server.stop()


class FakeWorkFolderClient:
    """Records calls and returns canned responses.

    Tests inspect `.calls` to assert the facet forwarded the right
    arguments to the work-folder backend. By default each tool returns
    a small dict shaped like the real work-folder MCP response.
    """

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._responses: dict[str, Any] = {}

    def set_response(self, tool_name: str, response: Any) -> None:
        self._responses[tool_name] = response

    async def call(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((tool_name, dict(arguments)))
        if tool_name in self._responses:
            return self._responses[tool_name]
        return {"tool": tool_name, "arguments": arguments, "ok": True}


@pytest.fixture
def fake_work_folder() -> FakeWorkFolderClient:
    return FakeWorkFolderClient()


@pytest.fixture
def bus_client(bus_double: Any) -> Any:
    from ronin_mcp.backends.agent_bus import AgentBusClient

    return AgentBusClient(bus_double.url, gateway_token="test-gateway-token-32-chars-minimum!")


class _StubEphemeralRuntime:
    """A test stub of EphemeralRuntime that reuses the in-process bus double.

    The real EphemeralRuntime spawns a subprocess; tests need the double
    (already started as a ThreadingHTTPServer) so the production httpx
    client can talk to it over real TCP. The stub exposes the same
    surface (bus_url / bus_gateway_token / work_folder_root / close) as
    EphemeralRuntime.
    """

    def __init__(
        self,
        bus_double: Any,
        work_folder_root: str,
    ) -> None:
        self._bus_double = bus_double
        self._work_folder_root = work_folder_root
        self._closed = False

    @property
    def bus_url(self) -> str:
        return self._bus_double.url

    @property
    def bus_gateway_token(self) -> str:
        return "test-gateway-token-32-chars-minimum!"

    @property
    def work_folder_root(self) -> str:
        return self._work_folder_root

    def close(self) -> None:
        self._closed = True


@pytest.fixture
def ephemeral_runtime(
    bus_double: Any,
    tmp_runs_root: str,
) -> Any:
    """An EphemeralRuntime-like stub wired to the in-process bus double."""
    return _StubEphemeralRuntime(bus_double, tmp_runs_root)


@pytest.fixture
def make_config() -> Any:
    """Factory for config dicts with the given auth flags."""
    from ronin_mcp.config import DEFAULT_CONFIG

    def _make(*, prod_write: bool = False, ephemeral: bool = False) -> dict[str, Any]:
        import copy

        config = copy.deepcopy(DEFAULT_CONFIG)
        config["auth"]["prod_write_enabled"] = prod_write
        config["auth"]["ephemeral"] = ephemeral
        return config

    return _make


@pytest.fixture
def mcp_server_factory(
    bus_client: Any,
    fake_work_folder: FakeWorkFolderClient,
) -> Any:
    """Factory that builds a FastMCP server with the doubles wired in."""
    from ronin_mcp.server import build_mcp_server

    def _build(
        config: dict[str, Any],
        *,
        ephemeral_runtime: Any = None,
    ) -> Any:
        return build_mcp_server(
            config,
            bus_client=bus_client,
            work_folder_client=fake_work_folder,
            ephemeral_runtime=ephemeral_runtime,
        )

    return _build


@pytest.fixture
def ephemeral_server_factory(
    bus_double: Any,
    tmp_runs_root: str,
) -> Any:
    """Factory that builds an ephemeral server backed by in-process doubles.

    Unlike ``mcp_server_factory``, this does NOT inject bus/work-folder
    clients: the server builds them from the ephemeral runtime's URL /
    temp root, so tests can assert that writes actually route to the
    ephemeral backends (not the configured production URLs).
    """
    from ronin_mcp.ephemeral import EphemeralRuntime
    from ronin_mcp.server import build_mcp_server

    def _make_bus_spawner(double: Any) -> Any:
        def _spawn() -> Any:
            return double.url, "test-gateway-token-32-chars-minimum!", double.stop

        return _spawn

    def _build(config: dict[str, Any]) -> Any:
        rt = EphemeralRuntime(
            bus_spawner=_make_bus_spawner(bus_double),
            work_folder_root=tmp_runs_root,
        )
        rt.start()
        return build_mcp_server(
            config,
            ephemeral_runtime=rt,
        ), rt

    return _build


@pytest.fixture
def in_memory_client(mcp_server_factory: Any, make_config: Any):
    """Build an in-memory FastMCP Client connected to the server.

    Defaults to a non-prod, non-ephemeral server. Tests that need a
    different auth state should call mcp_server_factory + _client_for
    directly.
    """
    from fastmcp import Client

    server = mcp_server_factory(make_config())
    client = Client(server)
    return client


def _run(coro: Any) -> Any:
    """Run an async coroutine in a fresh event loop."""
    return asyncio.run(coro)
