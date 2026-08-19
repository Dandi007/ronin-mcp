"""Loop-engine Controller HTTP client for Ronin MCP.

The Controller at 127.0.0.1 has no auth; delegation is carried via the
``X-Operator-Identity`` header (per the spec trust model).
"""

from __future__ import annotations

import json
from typing import Any, cast

import httpx

from ronin_mcp.backends.agent_bus import _BackendError


class DevDispatchClient:
    def __init__(self, base_url: str, *, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client = httpx.Client(trust_env=False)

    def close(self) -> None:
        self._client.close()

    def _headers(self, operator_identity: str | None) -> dict[str, str]:
        headers: dict[str, str] = {}
        if operator_identity:
            headers["X-Operator-Identity"] = operator_identity
        return headers

    def _unwrap(self, resp: httpx.Response, *, method: str, path: str) -> dict[str, Any]:
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
            raise _BackendError(
                "BACKEND_ERROR",
                f"controller {method} {path} failed with HTTP {resp.status_code}: {detail}",
                http_status=502,
            )
        try:
            return cast(dict[str, Any], resp.json())
        except ValueError as exc:
            raise _BackendError(
                "BACKEND_ERROR",
                f"controller {method} {path} returned invalid JSON: {exc}",
                http_status=502,
            ) from exc

    def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        operator_identity: str | None = None,
    ) -> dict[str, Any]:
        try:
            resp = self._client.get(
                f"{self._base_url}{path}",
                params=params,
                headers=self._headers(operator_identity),
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise _BackendError(
                "BACKEND_UNAVAILABLE",
                f"controller connection failed for GET {path}: {exc}",
                http_status=502,
            ) from exc
        return self._unwrap(resp, method="GET", path=path)

    def post(
        self,
        path: str,
        body: dict[str, Any],
        *,
        operator_identity: str | None = None,
    ) -> dict[str, Any]:
        try:
            resp = self._client.post(
                f"{self._base_url}{path}",
                json=body,
                headers=self._headers(operator_identity),
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise _BackendError(
                "BACKEND_UNAVAILABLE",
                f"controller connection failed for POST {path}: {exc}",
                http_status=502,
            ) from exc
        return self._unwrap(resp, method="POST", path=path)
