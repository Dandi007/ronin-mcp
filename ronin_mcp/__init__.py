"""Ronin MCP - aggregating facade for the ronin fleet control plane.

Exposes the ronin_* MCP namespace by aggregating two backends:
- agent-bus HTTP (alias / agent / channel / message / consume / ack)
- katana-work-folder MCP (work folder / file ops) via MCP client

The retired loop-engine Controller (development CRUD / gate / steer /
control) and the /data/ronin/runs pump-state filesystem reader were
removed outright (wf-525fd4 M3 follow-up: remove, do not redirect).

Write-side guardrails are enforced at the entrance: gd: prefix is allowed
freely, ephemeral mode unlocks everything, and production writes outside
the gd: namespace require explicit RONIN_PROD_WRITE=1 / --prod-write.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]