"""Process-local /metrics endpoint (spec 交付 1/2/3).

The ronin-mcp facade exposes a Prometheus-text /metrics route on the
ASGI app produced by ``build_mcp_server`` (via ``http_app()``). The
endpoint is auth-free and must never probe any backend/facet — it only
reports that the ronin-mcp process itself is up. This file also asserts
the existing ``/mcp`` route is not broken by the addition.
"""

from __future__ import annotations

from typing import Any

import pytest


@pytest.mark.timeout(30)
def test_metrics_endpoint_200_and_body(
    mcp_server_factory: Any, make_config: Any
) -> None:
    """GET /metrics returns 200 with the expected Prometheus text."""
    server = mcp_server_factory(make_config())
    app = server.http_app(path="/mcp")

    from starlette.testclient import TestClient

    with TestClient(app) as client:
        resp = client.get("/metrics")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert "version=0.0.4" in resp.headers["content-type"]
    assert "ronin_mcp_up 1" in resp.text
    assert "ronin_mcp_up" in resp.text
    assert "TYPE ronin_mcp_up gauge" in resp.text


@pytest.mark.timeout(30)
def test_metrics_endpoint_auth_free(
    mcp_server_factory: Any, make_config: Any
) -> None:
    """/metrics requires no auth token (it is a plain route)."""
    server = mcp_server_factory(make_config())
    app = server.http_app(path="/mcp")

    from starlette.testclient import TestClient

    with TestClient(app) as client:
        resp = client.get("/metrics", headers={"Authorization": ""})

    assert resp.status_code == 200
    assert "ronin_mcp_up 1" in resp.text


@pytest.mark.timeout(30)
def test_metrics_does_not_touch_backends(
    mcp_server_factory: Any,
    make_config: Any,
    bus_double: Any,
    fake_work_folder: Any,
) -> None:
    """Calling /metrics must not produce any backend traffic.

    The endpoint is process-local: it reports ronin_mcp's own liveness
    and must never probe agent-bus / work-folder.
    """
    server = mcp_server_factory(make_config())
    app = server.http_app(path="/mcp")

    from starlette.testclient import TestClient

    with TestClient(app) as client:
        resp = client.get("/metrics")

    assert resp.status_code == 200
    assert resp.text.strip().endswith("ronin_mcp_up 1")

    # The HTTP double records every request it served; /metrics must
    # not have added any backend calls.
    assert len(bus_double.requests) == 0, "agent-bus was probed by /metrics"
    assert fake_work_folder.calls == [], "work-folder was probed by /metrics"


@pytest.mark.timeout(30)
def test_mcp_endpoint_still_served(mcp_server_factory: Any, make_config: Any) -> None:
    """Regression: the existing /mcp endpoint is still mounted."""
    server = mcp_server_factory(make_config())
    app = server.http_app(path="/mcp")

    from starlette.testclient import TestClient

    with TestClient(app) as client:
        resp = client.get("/mcp")

    # The /mcp route is still present (a plain GET is a protocol error,
    # but must never 404).
    assert resp.status_code != 404


@pytest.mark.timeout(30)
def test_metrics_ephemeral_mode(mcp_server_factory: Any, make_config: Any) -> None:
    """Ephemeral mode still serves /metrics (no semantic change)."""
    server = mcp_server_factory(make_config(ephemeral=True))
    app = server.http_app(path="/mcp")

    from starlette.testclient import TestClient

    with TestClient(app) as client:
        resp = client.get("/metrics")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert "version=0.0.4" in resp.headers["content-type"]
    assert "ronin_mcp_up 1" in resp.text
