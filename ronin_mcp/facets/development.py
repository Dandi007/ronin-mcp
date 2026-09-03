"""Development (dd dispatch) facet — removed.

The ``ronin_dev_*`` tools (list / get / events / evidence / create / start /
steer / reconfigure / control / relock) are no longer part of ronin-mcp's
surface. They are removed from the registry entirely and no longer appear
in ``tools/list``.
"""

from __future__ import annotations

from typing import Any


def register(
    mcp: Any,
    auth: Any,
    controller: Any,
    error_wrapper: Any,
) -> None:
    """No-op: the ronin_dev_* tools have been removed from the registry."""