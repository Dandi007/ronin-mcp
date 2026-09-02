"""Agent-bus HTTP client.

Mirrors the _bus_get / _bus_post / _bus_delete helpers from
agent_bus/mcp_gateway.py so the facets can compose agent-bus endpoints
without re-implementing header injection or error wrapping.

The client is transport-agnostic: tests inject an httpx.MockTransport
while production uses a plain httpx.Client(trust_env=False).

Backend errors surface as ``BackendError`` carrying the canonical
``{code, message, details: {retryable}}`` envelope required by
spec §错误模型. Unreachable backends are distinguished from backends
that returned an error response: the former is ``BACKEND_UNAVAILABLE``
(retryable=True) and the latter is ``BACKEND_ERROR`` (retryable depends
on the HTTP status: 5xx is retryable, 4xx is not).
"""

from __future__ import annotations

import json
from typing import Any, cast

import httpx


class BackendError(Exception):
    """Raised when a backend returns a non-2xx response or is unreachable.

    Carries the canonical error envelope (spec §错误模型) so the server
    layer can surface it to the caller as a structured MCP error:

        {
          "code": "BACKEND_ERROR" | "BACKEND_UNAVAILABLE",
          "message": "...",
          "details": {"retryable": bool}
        }
    """

    def __init__(
        self,
        message: str,
        *,
        code: str,
        status_code: int = 0,
        payload: Any = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.payload = payload
        self.retryable = retryable

    @property
    def envelope(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": str(self),
            "details": {"retryable": self.retryable},
        }


class AgentBusClient:
    """HTTP client for agent-bus (alias / agent / channel / message / consume)."""

    def __init__(
        self,
        base_url: str,
        gateway_token: str = "",
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._gateway_token = gateway_token
        self._client = client or httpx.Client(trust_env=False)

    @property
    def base_url(self) -> str:
        return self._base_url

    def _headers(self, as_agent_id: str | None = None) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._gateway_token:
            headers["Authorization"] = f"Bearer {self._gateway_token}"
        if as_agent_id:
            headers["X-Bus-On-Behalf-Of"] = as_agent_id
        return headers

    def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            resp = self._client.get(
                f"{self._base_url}{path}",
                params=params,
                headers=self._headers(as_agent_id),
                timeout=30.0,
            )
        except httpx.RequestError as exc:
            raise BackendError(
                f"agent-bus GET {path} unavailable: {exc}",
                code="BACKEND_UNAVAILABLE",
                retryable=True,
            ) from exc
        return _handle_response(resp, path, "GET")

    def post(
        self,
        path: str,
        body: dict[str, Any],
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            resp = self._client.post(
                f"{self._base_url}{path}",
                json=body,
                headers=self._headers(as_agent_id),
                timeout=30.0,
            )
        except httpx.RequestError as exc:
            raise BackendError(
                f"agent-bus POST {path} unavailable: {exc}",
                code="BACKEND_UNAVAILABLE",
                retryable=True,
            ) from exc
        return _handle_response(resp, path, "POST")

    def delete(
        self,
        path: str,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        try:
            resp = self._client.delete(
                f"{self._base_url}{path}",
                headers=self._headers(as_agent_id),
                timeout=30.0,
            )
        except httpx.RequestError as exc:
            raise BackendError(
                f"agent-bus DELETE {path} unavailable: {exc}",
                code="BACKEND_UNAVAILABLE",
                retryable=True,
            ) from exc
        return _handle_response(resp, path, "DELETE")

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
        retryable = 500 <= resp.status_code < 600
        raise BackendError(
            f"agent-bus {method} {path} failed with HTTP {resp.status_code}: {detail}",
            code="BACKEND_ERROR",
            status_code=resp.status_code,
            payload=payload,
            retryable=retryable,
        )
    try:
        return cast(dict[str, Any], resp.json())
    except ValueError as exc:
        raise BackendError(
            f"agent-bus {method} {path} returned invalid JSON: {exc}",
            code="BACKEND_ERROR",
            status_code=resp.status_code,
            retryable=False,
        ) from exc
