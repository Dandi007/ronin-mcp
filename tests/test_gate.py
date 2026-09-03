"""Gate-approval facet (B-class irreversible operations) — removed.

``ronin_gate_approve`` / ``ronin_gate_reject`` are removed from the
registry. This file asserts they are absent from
``create_server().list_tools()``: no tool with the ``ronin_gate_`` prefix
may remain registered.
"""

from __future__ import annotations

from typing import Any

import pytest

from ronin_mcp.server import create_server

DEAD_GATE_TOOLS = [
    "ronin_gate_approve",
    "ronin_gate_reject",
]


@pytest.fixture(scope="module")
def registered_names() -> set[str]:
    return {t.name for t in create_server().list_tools()}


@pytest.mark.timeout(30)
def test_gate_tools_are_absent_from_registry(registered_names: set[str]) -> None:
    """No ronin_gate_* tool remains registered."""
    assert not any(name.startswith("ronin_gate_") for name in registered_names)


@pytest.mark.timeout(30)
@pytest.mark.parametrize("tool_name", DEAD_GATE_TOOLS)
def test_each_dead_gate_tool_is_absent(
    tool_name: str, registered_names: set[str]
) -> None:
    """Every formerly-registered ronin_gate_* tool is gone."""
    assert tool_name not in registered_names