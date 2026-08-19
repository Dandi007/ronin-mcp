"""Agent-bus HTTP client for Ronin MCP.

Mirrors the agent-bus ``mcp_gateway`` request helpers: a shared
``httpx.Client``, ``Authorization: Bearer <gateway-token>`` plus
``X-Bus-On-Behalf-Of`` delegation, and uniform error wrapping into
``ToolError``.
"""

from __future__ import annotations

import json
from typing import Any, cast

import httpx


class AgentBusClient:
    def __init__(self, base_url: str, gateway_token: str, *, timeout: float = 30.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._gateway_token = gateway_token
        self._timeout = timeout
        self._client = httpx.Client(trust_env=False)

    def close(self) -> None:
        self._client.close()

    def _headers(self, as_agent_id: str | None) -> dict[str, str]:
        headers: dict[str, str] = {"Authorization": f"Bearer {self._gateway_token}"}
        if as_agent_id:
            headers["X-Bus-On-Behalf-Of"] = as_agent_id
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
                f"agent-bus {method} {path} failed with HTTP {resp.status_code}: {detail}",
                http_status=502,
            )
        try:
            return cast(dict[str, Any], resp.json())
        except ValueError as exc:
            raise _BackendError(
                "BACKEND_ERROR",
                f"agent-bus {method} {path} returned invalid JSON: {exc}",
                http_status=502,
            ) from exc

    def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            resp = self._client.get(
                f"{self._base_url}{path}",
                params=params,
                headers=self._headers(as_agent_id),
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise _BackendError(
                "BACKEND_UNAVAILABLE",
                f"agent-bus connection failed for GET {path}: {exc}",
                http_status=502,
            ) from exc
        return self._unwrap(resp, method="GET", path=path)

    def post(
        self,
        path: str,
        body: dict[str, Any],
        *,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            resp = self._client.post(
                f"{self._base_url}{path}",
                json=body,
                headers=self._headers(as_agent_id),
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise _BackendError(
                "BACKEND_UNAVAILABLE",
                f"agent-bus connection failed for POST {path}: {exc}",
                http_status=502,
            ) from exc
        return self._unwrap(resp, method="POST", path=path)

    def delete(
        self,
        path: str,
        *,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            resp = self._client.delete(
                f"{self._base_url}{path}",
                headers=self._headers(as_agent_id),
                timeout=self._timeout,
            )
        except httpx.HTTPError as exc:
            raise _BackendError(
                "BACKEND_UNAVAILABLE",
                f"agent-bus connection failed for DELETE {path}: {exc}",
                http_status=502,
            ) from exc
        return self._unwrap(resp, method="DELETE", path=path)


class _BackendError(Exception):
    def __init__(self, code: str, message: str, *, http_status: int = 502) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details: dict[str, Any] = {"retryable": False}

    def as_error_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


def backend_error(code: str, message: str, *, http_status: int = 502) -> _BackendError:
    return _BackendError(code, message, http_status=http_status)
