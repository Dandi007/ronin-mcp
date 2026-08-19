"""Katana work-folder MCP client for Ronin MCP.

ronin-mcp proxies work-folder / file operations to the katana-work-folder
MCP server via a real MCP client (streamable-http). The client is created
lazily so a missing backend surfaces as ``BACKEND_UNAVAILABLE`` rather than
crashing server build.
"""

from __future__ import annotations

from typing import Any

from ronin_mcp.backends.agent_bus import _BackendError


class WorkFolderClient:
    def __init__(self, mcp_url: str) -> None:
        self._mcp_url = mcp_url

    def _client(self) -> Any:
        try:
            from fastmcp import Client
        except ImportError as exc:
            raise _BackendError(
                "BACKEND_UNAVAILABLE",
                f"fastmcp client unavailable: {exc}",
                http_status=502,
            ) from exc
        return Client(self._mcp_url)

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        import asyncio

        async def _invoke() -> Any:
            try:
                async with self._client() as client:
                    result = await client.call_tool(name, arguments)
            except Exception as exc:
                raise _BackendError(
                    "BACKEND_UNAVAILABLE",
                    f"work-folder MCP call {name} failed: {exc}",
                    http_status=502,
                ) from exc
            return _tool_result_to_dict(result)

        try:
            return asyncio.run(_invoke())
        except _BackendError:
            raise
        except RuntimeError as exc:
            if "event loop" in str(exc).lower():
                return _call_in_thread(self._mcp_url, name, arguments)
            raise _BackendError(
                "BACKEND_UNAVAILABLE",
                f"work-folder MCP call {name} failed: {exc}",
                http_status=502,
            ) from exc


def _tool_result_to_dict(result: Any) -> dict[str, Any]:
    sc = getattr(result, "structured_content", None)
    if sc is not None:
        return sc if isinstance(sc, dict) else {"result": sc}
    content = getattr(result, "content", None)
    if content:
        first = content[0]
        text = getattr(first, "text", None)
        if text is not None:
            return {"text": text}
    return {"result": str(result)}


def _call_in_thread(mcp_url: str, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    import asyncio
    import threading

    box: dict[str, Any] = {}

    def _runner() -> None:
        from fastmcp import Client

        async def _invoke() -> Any:
            try:
                async with Client(mcp_url) as client:
                    result = await client.call_tool(name, arguments)
            except Exception as exc:
                box["error"] = _BackendError(
                    "BACKEND_UNAVAILABLE",
                    f"work-folder MCP call {name} failed: {exc}",
                    http_status=502,
                )
                return None
            return _tool_result_to_dict(result)

        try:
            box["result"] = asyncio.run(_invoke())
        except BaseException as exc:
            box["error"] = _BackendError(
                "BACKEND_UNAVAILABLE",
                f"work-folder MCP call {name} failed: {exc}",
                http_status=502,
            )

    t = threading.Thread(target=_runner)
    t.start()
    t.join()
    if "error" in box:
        raise box["error"]
    return box.get("result", {})
