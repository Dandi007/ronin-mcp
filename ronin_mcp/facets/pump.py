"""Pump-state facet (read-only /data/ronin/runs/) — removed.

The ``ronin_pump_*`` tools (list / get / rounds) are no longer part of
ronin-mcp's surface. They are removed from the registry entirely and no
longer appear in ``tools/list``.
"""

from __future__ import annotations

from typing import Any


def register(
    mcp: Any,
    pump: Any,
    error_wrapper: Any,
) -> None:
    """No-op: the ronin_pump_* tools have been removed from the registry."""