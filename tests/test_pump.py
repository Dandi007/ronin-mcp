"""Pump-state facet (read-only /data/ronin/runs/) — removed.

The ``ronin_pump_*`` tools (3) are removed from the registry. This file
asserts they are absent from ``create_server().list_tools()``: no tool
with the ``ronin_pump_`` prefix may remain registered.
"""

from __future__ import annotations

from typing import Any

import pytest

from ronin_mcp.server import create_server

DEAD_PUMP_TOOLS = [
    "ronin_pump_list",
    "ronin_pump_get",
    "ronin_pump_rounds",
]


@pytest.fixture(scope="module")
def registered_names() -> set[str]:
    return {t.name for t in create_server().list_tools()}


@pytest.mark.timeout(30)
def test_pump_tools_are_absent_from_registry(registered_names: set[str]) -> None:
    """No ronin_pump_* tool remains registered."""
    assert not any(name.startswith("ronin_pump_") for name in registered_names)


@pytest.mark.timeout(30)
@pytest.mark.parametrize("tool_name", DEAD_PUMP_TOOLS)
def test_each_dead_pump_tool_is_absent(
    tool_name: str, registered_names: set[str]
) -> None:
    """Every formerly-registered ronin_pump_* tool is gone."""
    assert tool_name not in registered_names