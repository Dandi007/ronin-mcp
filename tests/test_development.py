"""Development (dd dispatch) facet — removed surface.

The ``ronin_dev_*`` tools (10) are removed from the registry. This file
asserts they are absent from ``create_server().list_tools()``: no tool
with the ``ronin_dev_`` prefix may remain registered.
"""

from __future__ import annotations

from typing import Any

import pytest

from ronin_mcp.server import create_server

DEAD_DEV_TOOLS = [
    "ronin_dev_list",
    "ronin_dev_get",
    "ronin_dev_events",
    "ronin_dev_evidence",
    "ronin_dev_create",
    "ronin_dev_start",
    "ronin_dev_steer",
    "ronin_dev_reconfigure",
    "ronin_dev_control",
    "ronin_dev_relock",
]


@pytest.fixture(scope="module")
def registered_names() -> set[str]:
    return {t.name for t in create_server().list_tools()}


@pytest.mark.timeout(30)
def test_dev_tools_are_absent_from_registry(registered_names: set[str]) -> None:
    """No ronin_dev_* tool remains registered."""
    assert not any(name.startswith("ronin_dev_") for name in registered_names)


@pytest.mark.timeout(30)
@pytest.mark.parametrize("tool_name", DEAD_DEV_TOOLS)
def test_each_dead_dev_tool_is_absent(
    tool_name: str, registered_names: set[str]
) -> None:
    """Every formerly-registered ronin_dev_* tool is gone."""
    assert tool_name not in registered_names