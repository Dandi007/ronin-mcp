"""Structured backend error model (spec §错误模型).

The entrance must surface backend errors as the canonical structured
envelope, not a plain string message:

    {"code": "BACKEND_ERROR" | "BACKEND_UNAVAILABLE",
     "message": "...",
     "details": {"retryable": bool}}

BACKEND_UNAVAILABLE (backend unreachable) is distinguished from
BACKEND_ERROR (backend returned an error response).
"""

from __future__ import annotations

import asyncio
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError


def _extract_text(result: Any) -> str:
    if hasattr(result, "content") and result.content:
        return result.content[0].text
    if hasattr(result, "text"):
        return result.text
    return str(result)


def _error_envelope(exc: ToolError) -> dict[str, Any]:
    """Parse the structured envelope from a ToolError message."""
    raw = str(exc)
    # FastMCP prefixes ToolError messages; the JSON payload we set in
    # _make_error_wrapper is still a substring.
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {"raw": raw}
    return json.loads(raw[start : end + 1])


class _ErrorBusHandler(BaseHTTPRequestHandler):
    """A bus double that always returns 500 on /v1/aliases."""

    def log_message(self, format: str, *args: object) -> None:
        pass

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/")
        if path == "/v1/aliases":
            body = json.dumps({"code": "INTERNAL", "message": "boom"}).encode()
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()


class _NotFoundBusHandler(BaseHTTPRequestHandler):
    """A bus double that always returns 404 on /v1/aliases."""

    def log_message(self, format: str, *args: object) -> None:
        pass

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/")
        if path == "/v1/aliases":
            body = json.dumps({"code": "NOT_FOUND", "message": "no aliases"}).encode()
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()


def _boot_double(handler_cls: type) -> tuple[str, ThreadingHTTPServer, Any]:
    """Boot a ThreadingHTTPServer on an OS-assigned port and return (url, srv, thread)."""
    import threading
    import time

    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler_cls)
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    # Let the server bind.
    time.sleep(0.05)
    return url, srv, thread


@pytest.mark.timeout(30)
def test_backend_unreachable_surfaces_as_BACKEND_UNAVAILABLE_and_retryable(
    mcp_server_factory: Any, make_config: Any
) -> None:
    """An unreachable bus surfaces as BACKEND_UNAVAILABLE with retryable=True."""
    from ronin_mcp.backends.agent_bus import AgentBusClient
    from ronin_mcp.server import build_mcp_server

    unreachable_bus = AgentBusClient("http://127.0.0.1:1", gateway_token="x" * 32)
    server = build_mcp_server(
        make_config(),
        bus_client=unreachable_bus,
        # controller / work_folder doubles are wired by the factory but
        # we only exercise the bus leg here.
        controller_client=None,
        work_folder_client=None,
        pump_client=None,
    )

    async def _run() -> None:
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc:
                await client.call_tool("ronin_alias_list", {})
            env = _error_envelope(exc.value)
            assert env["code"] == "BACKEND_UNAVAILABLE"
            assert env["details"]["retryable"] is True

    asyncio.run(_run())


@pytest.mark.timeout(30)
def test_backend_error_response_surfaces_as_BACKEND_ERROR() -> None:
    """A 5xx backend response surfaces as BACKEND_ERROR with retryable=True."""
    from ronin_mcp.backends.agent_bus import AgentBusClient
    from ronin_mcp.config import DEFAULT_CONFIG
    from ronin_mcp.server import build_mcp_server

    url, srv, thread = _boot_double(_ErrorBusHandler)
    try:
        import copy

        config = copy.deepcopy(DEFAULT_CONFIG)
        config["auth"]["prod_write_enabled"] = False
        config["auth"]["ephemeral"] = False
        bus = AgentBusClient(url, gateway_token="x" * 32)
        server = build_mcp_server(
            config,
            bus_client=bus,
            controller_client=None,
            work_folder_client=None,
            pump_client=None,
        )

        async def _run() -> None:
            async with Client(server) as client:
                with pytest.raises(ToolError) as exc:
                    await client.call_tool("ronin_alias_list", {})
                env = _error_envelope(exc.value)
                assert env["code"] == "BACKEND_ERROR"
                assert "500" in env["message"]
                assert env["details"]["retryable"] is True

        asyncio.run(_run())
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=2)


@pytest.mark.timeout(30)
def test_backend_4xx_is_BACKEND_ERROR_not_retryable() -> None:
    """A 4xx backend response is BACKEND_ERROR with retryable=False."""
    from ronin_mcp.backends.agent_bus import AgentBusClient
    from ronin_mcp.config import DEFAULT_CONFIG
    from ronin_mcp.server import build_mcp_server

    url, srv, thread = _boot_double(_NotFoundBusHandler)
    try:
        import copy

        config = copy.deepcopy(DEFAULT_CONFIG)
        config["auth"]["prod_write_enabled"] = False
        config["auth"]["ephemeral"] = False
        bus = AgentBusClient(url, gateway_token="x" * 32)
        server = build_mcp_server(
            config,
            bus_client=bus,
            controller_client=None,
            work_folder_client=None,
            pump_client=None,
        )

        async def _run() -> None:
            async with Client(server) as client:
                with pytest.raises(ToolError) as exc:
                    await client.call_tool("ronin_alias_list", {})
                env = _error_envelope(exc.value)
                assert env["code"] == "BACKEND_ERROR"
                assert env["details"]["retryable"] is False

        asyncio.run(_run())
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=2)


@pytest.mark.timeout(30)
def test_backend_unavailable_controller_surfaces_as_BACKEND_UNAVAILABLE(
    mcp_server_factory: Any, make_config: Any
) -> None:
    """An unreachable Controller surfaces as BACKEND_UNAVAILABLE."""
    from ronin_mcp.backends.dev_dispatch import DevDispatchClient
    from ronin_mcp.server import build_mcp_server

    unreachable_ctrl = DevDispatchClient("http://127.0.0.1:1")
    server = build_mcp_server(
        make_config(),
        bus_client=None,
        controller_client=unreachable_ctrl,
        work_folder_client=None,
        pump_client=None,
    )

    async def _run() -> None:
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc:
                await client.call_tool("ronin_dev_list", {})
            env = _error_envelope(exc.value)
            assert env["code"] == "BACKEND_UNAVAILABLE"
            assert env["details"]["retryable"] is True

    asyncio.run(_run())


@pytest.mark.timeout(30)
def test_backend_error_envelope_shape(mcp_server_factory: Any, make_config: Any) -> None:
    """The structured envelope always carries code/message/details.retryable."""
    from ronin_mcp.backends.agent_bus import AgentBusClient
    from ronin_mcp.server import build_mcp_server

    unreachable_bus = AgentBusClient("http://127.0.0.1:1", gateway_token="x" * 32)
    server = build_mcp_server(
        make_config(),
        bus_client=unreachable_bus,
        controller_client=None,
        work_folder_client=None,
        pump_client=None,
    )

    async def _run() -> None:
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc:
                await client.call_tool("ronin_alias_list", {})
            env = _error_envelope(exc.value)
            assert set(env.keys()) == {"code", "message", "details"}
            assert set(env["details"].keys()) == {"retryable"}
            assert isinstance(env["message"], str)
            assert isinstance(env["details"]["retryable"], bool)

    asyncio.run(_run())
