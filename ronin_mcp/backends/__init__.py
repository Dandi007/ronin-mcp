"""Backend clients for Ronin MCP.

Each backend wraps a single transport (agent-bus HTTP, or the
katana-work-folder MCP client) and exposes a small set of low-level
methods the facets compose into tools.

The clients never carry credentials in their public method signatures;
authorization headers are injected from server-level config.
"""

from __future__ import annotations

__all__: list[str] = []