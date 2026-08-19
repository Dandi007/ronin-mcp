"""Work-folder backend (katana-work-folder MCP client).

Talks to the katana-work-folder MCP server over streamable-http. Each
facade tool is a thin passthrough: the ronin_wf_* / ronin_fs_* surface
maps 1:1 to the underlying MCP tool of the same (wf_* / fs_*) name.

The client is a thin async wrapper around fastmcp.Client so that the
facets can call tools with native Python signatures and have the result
returned as a dict / list.
"""

from __future__ import annotations

import asyncio
from typing import Any


class WorkFolderClient:
    """Async MCP client for katana-work-folder MCP.

    The client wraps a fastmcp.Client connected to the configured
    mcp_url. Each method opens a short-lived session, calls one tool,
    and returns the structured content as a Python object.

    Tests substitute this client with a fake that records calls and
    returns canned responses; production wires the real fastmcp.Client.
    """

    def __init__(self, mcp_url: str, *, client_factory: Any = None) -> None:
        self._mcp_url = mcp_url
        self._client_factory = client_factory

    @property
    def mcp_url(self) -> str:
        return self._mcp_url

    async def call(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Invoke a single tool on the work-folder MCP and return its content.

        Returns the first text content item parsed as JSON when the
        result carries structured text content; otherwise returns the
        raw structured payload.
        """
        if self._client_factory is not None:
            client = self._client_factory(self._mcp_url)
        else:
            from fastmcp import Client  # local import keeps tests fast

            client = Client(self._mcp_url)

        async with client:
            result = await client.call_tool(tool_name, arguments)
        return _extract_content(result)

    def call_sync(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Synchronous wrapper for use from non-async facets."""
        return asyncio.run(self.call(tool_name, arguments))


def _extract_content(result: Any) -> Any:
    """Extract a Python object from a fastmcp CallToolResult.

    FastMCP returns CallToolResult with .content (list of TextContent).
    We parse the first text item as JSON when possible; otherwise we
    return the raw text. This mirrors the agent-bus test helper.
    """
    if hasattr(result, "content") and result.content:
        first = result.content[0]
        text = getattr(first, "text", None)
        if text is None:
            return first
        try:
            import json

            return json.loads(text)
        except (ValueError, TypeError):
            return text
    if hasattr(result, "text"):
        return result.text
    return result
