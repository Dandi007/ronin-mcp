"""Dead tool removal (wf-525fd4 M3 follow-up: remove, do not redirect).

The retired dd-dispatch / gate / pump surfaces were removed outright.
Their tools must no longer appear in the server's ``list_tools`` output
(no ``ronin_dev_*`` / ``ronin_gate_*`` / ``ronin_pump_*`` names), while
the live agent-bus / work-folder surfaces stay fully registered.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastmcp import Client

RETIRED_TOOL_NAMES = {
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
    "ronin_gate_approve",
    "ronin_gate_reject",
    "ronin_pump_list",
    "ronin_pump_get",
    "ronin_pump_rounds",
}

LIVE_TOOL_NAMES = {
    "ronin_alias_list",
    "ronin_alias_register",
    "ronin_agent_register",
    "ronin_chatgroup_create",
    "ronin_msg_send",
    "ronin_wf_list",
    "ronin_fs_read",
}


def _server_tool_names(server: Any) -> set[str]:
    async def _run() -> set[str]:
        async with Client(server) as client:
            return {t.name for t in await client.list_tools()}

    return asyncio.run(_run())


@pytest.mark.timeout(30)
def test_retired_tools_are_not_registered(
    mcp_server_factory: Any, make_config: Any
) -> None:
    """The retired dev / gate / pump tools are gone from tools/list."""
    server = mcp_server_factory(make_config())
    names = _server_tool_names(server)
    assert names.isdisjoint(RETIRED_TOOL_NAMES), names & RETIRED_TOOL_NAMES


@pytest.mark.timeout(30)
def test_live_tools_remain_registered(
    mcp_server_factory: Any, make_config: Any
) -> None:
    """The live agent-bus / work-folder tools are still registered."""
    server = mcp_server_factory(make_config())
    names = _server_tool_names(server)
    assert LIVE_TOOL_NAMES.issubset(names), LIVE_TOOL_NAMES - names


@pytest.mark.timeout(30)
def test_create_server_lists_no_retired_tools() -> None:
    """create_server().list_tools() (the acceptance probe) has no retired names."""
    from ronin_mcp.server import create_server

    server = create_server()
    names = {t.name for t in server.list_tools()}
    assert names.isdisjoint(RETIRED_TOOL_NAMES), names & RETIRED_TOOL_NAMES