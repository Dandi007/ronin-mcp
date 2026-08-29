"""GET /metrics custom route (spec: ronin-mcp 仓侧 /metrics 接入).

Builds a server via build_mcp_server (conftest mcp_server_factory),
exposes it over FastMCP http_app(), and drives it with httpx
ASGITransport. Asserts /metrics returns 200, a text/plain content-type
carrying version=0.0.4, and a body containing "ronin_mcp_up 1".
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx


def _get_metrics(server: Any) -> httpx.Response:
    app = server.http_app()
    transport = httpx.ASGITransport(app=app)

    async def _run() -> httpx.Response:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            return await client.get("/metrics")

    return asyncio.run(_run())


def test_metrics_endpoint(mcp_server_factory: Any, make_config: Any) -> None:
    server = mcp_server_factory(make_config())
    resp = _get_metrics(server)

    assert resp.status_code == 200

    content_type = resp.headers["content-type"]
    assert content_type.startswith("text/plain")
    assert "version=0.0.4" in content_type

    assert "ronin_mcp_up 1" in resp.text
