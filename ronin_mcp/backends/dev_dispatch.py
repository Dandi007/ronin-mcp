"""Loop-engine Controller HTTP client.

Wraps the development CRUD / gate / steer / control endpoints exposed
by the loop-engine-development-mcp Controller. The Controller has no
authentication (it binds 127.0.0.1); ronin-mcp injects an
X-Operator-Identity header from the as_agent_id parameter so the
Controller can record the operator on whose behalf a mutation was made.
"""

from __future__ import annotations

import json
from typing import Any, cast

import httpx

from ronin_mcp.backends.agent_bus import BackendError


class DevDispatchClient:
    """HTTP client for the loop-engine Controller."""

    def __init__(
        self,
        base_url: str,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(trust_env=False)

    @property
    def base_url(self) -> str:
        return self._base_url

    def _headers(self, as_agent_id: str | None = None) -> dict[str, str]:
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if as_agent_id:
            headers["X-Operator-Identity"] = as_agent_id
        return headers

    def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        resp = self._client.get(
            f"{self._base_url}{path}",
            params=params,
            headers=self._headers(as_agent_id),
            timeout=30.0,
        )
        return _handle_response(resp, path, "GET")

    def post(
        self,
        path: str,
        body: dict[str, Any],
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        resp = self._client.post(
            f"{self._base_url}{path}",
            json=body,
            headers=self._headers(as_agent_id),
            timeout=30.0,
        )
        return _handle_response(resp, path, "POST")

    def close(self) -> None:
        self._client.close()


def _handle_response(resp: httpx.Response, path: str, method: str) -> dict[str, Any]:
    if not 200 <= resp.status_code < 300:
        try:
            payload: Any = resp.json()
        except ValueError:
            payload = resp.text
        detail = (
            json.dumps(payload, ensure_ascii=False)
            if not isinstance(payload, str)
            else payload
        )
        raise BackendError(
            f"controller {method} {path} failed with HTTP {resp.status_code}: {detail}",
            status_code=resp.status_code,
            payload=payload,
        )
    try:
        return cast(dict[str, Any], resp.json())
    except ValueError as exc:
        raise BackendError(
            f"controller {method} {path} returned invalid JSON: {exc}",
            status_code=resp.status_code,
        ) from exc
