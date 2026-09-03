"""Ronin MCP facets.

A facet is a coherent slice of the ronin_* tool surface. Each facet
module exports a `register(server, auth, backends)` function that
decorates tools onto a FastMCP instance using the shared auth state and
the backend clients. This keeps the per-facet tool definitions small
and co-located with the backend they wrap.
"""

from __future__ import annotations

__all__: list[str] = []
