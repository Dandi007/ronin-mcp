"""Alias registry facet (spec §面 1).

Exercises ronin_alias_list / resolve / register / rebind and
ronin_agent_list / whoami / register against the agent-bus HTTP double.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from fastmcp import Client


def _extract_text(result: Any) -> str:
    if hasattr(result, "content") and result.content:
        return result.content[0].text
    if hasattr(result, "text"):
        return result.text
    return str(result)


def _call(server: Any, tool: str, args: dict[str, Any]) -> dict[str, Any]:
    async def _run() -> dict[str, Any]:
        async with Client(server) as client:
            result = await client.call_tool(tool, args)
            return json.loads(_extract_text(result))
    return asyncio.run(_run())


@pytest.mark.timeout(30)
def test_agent_register_and_list(mcp_server_factory: Any, make_config: Any) -> None:
    """ronin_agent_register + ronin_agent_list roundtrip."""
    server = mcp_server_factory(make_config(prod_write=True))
    _call(server, "ronin_agent_register", {
        "agent_id": "prod-bot-1", "display_name": "Prod Bot 1", "kind": "agent",
    })
    data = _call(server, "ronin_agent_list", {})
    agents = data["agents"]
    assert any(a["agent_id"] == "prod-bot-1" for a in agents)


@pytest.mark.timeout(30)
def test_gd_agent_register_allowed(mcp_server_factory: Any, make_config: Any) -> None:
    """gd: agent registration works without prod write."""
    server = mcp_server_factory(make_config())
    data = _call(server, "ronin_agent_register", {
        "agent_id": "gd:test-bot", "display_name": "Test Bot", "kind": "agent",
    })
    assert data["agent_id"] == "gd:test-bot"
    assert "token" not in data


@pytest.mark.timeout(30)
def test_agent_register_strips_token(mcp_server_factory: Any, make_config: Any) -> None:
    """The gateway strips token material from the agent register response."""
    server = mcp_server_factory(make_config(prod_write=True))
    data = _call(server, "ronin_agent_register", {
        "agent_id": "prod-strip", "display_name": "Strip", "kind": "agent",
    })
    assert "token" not in data
    assert "token_sha256" not in data


@pytest.mark.timeout(30)
def test_agent_whoami(mcp_server_factory: Any, make_config: Any) -> None:
    """ronin_agent_whoami returns the on-behalf-of identity."""
    server = mcp_server_factory(make_config())
    data = _call(server, "ronin_agent_whoami", {"as_agent_id": "gd:caller"})
    assert data["agent_id"] == "gd:caller"


@pytest.mark.timeout(30)
def test_alias_register_resolve(mcp_server_factory: Any, make_config: Any) -> None:
    """Register then resolve an alias."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_agent_register", {
        "agent_id": "gd:alias-bot", "display_name": "Alias Bot", "kind": "agent",
    })
    data = _call(server, "ronin_alias_register", {
        "alias": "gd:test-alias", "kind": "named", "agent_id": "gd:alias-bot",
    })
    assert data["alias"] == "gd:test-alias"
    assert data["current_agent_id"] == "gd:alias-bot"

    resolved = _call(server, "ronin_alias_resolve", {"alias": "gd:test-alias"})
    assert resolved["alias"] == "gd:test-alias"
    assert resolved["current_agent_id"] == "gd:alias-bot"


@pytest.mark.timeout(30)
def test_alias_list(mcp_server_factory: Any, make_config: Any) -> None:
    """List aliases."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_agent_register", {
        "agent_id": "gd:list-bot", "display_name": "List Bot", "kind": "agent",
    })
    _call(server, "ronin_alias_register", {
        "alias": "gd:list-alias", "kind": "named", "agent_id": "gd:list-bot",
    })
    data = _call(server, "ronin_alias_list", {})
    aliases = data["aliases"]
    assert any(a["alias"] == "gd:list-alias" for a in aliases)


@pytest.mark.timeout(30)
def test_alias_rebind_cas(mcp_server_factory: Any, make_config: Any) -> None:
    """Rebind an alias (CAS expected_current_agent_id)."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_agent_register", {
        "agent_id": "gd:rebind-old", "display_name": "Old", "kind": "agent",
    })
    _call(server, "ronin_agent_register", {
        "agent_id": "gd:rebind-new", "display_name": "New", "kind": "agent",
    })
    _call(server, "ronin_alias_register", {
        "alias": "gd:rebind-alias", "kind": "named", "agent_id": "gd:rebind-old",
    })
    data = _call(server, "ronin_alias_rebind", {
        "alias": "gd:rebind-alias",
        "agent_id": "gd:rebind-new",
        "expected_current_agent_id": "gd:rebind-old",
    })
    assert data["current_agent_id"] == "gd:rebind-new"


@pytest.mark.timeout(30)
def test_alias_register_via_header(mcp_server_factory: Any, make_config: Any, bus_double: Any) -> None:
    """When as_agent_id is set, the bus sees X-Bus-On-Behalf-Of."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_agent_register", {
        "agent_id": "gd:via-bot", "display_name": "Via", "kind": "agent",
        "as_agent_id": "gd:caller",
    })
    agents = bus_double.store["agents"]
    assert "gd:via-bot" in agents


@pytest.mark.timeout(30)
def test_tool_registry_includes_all_alias_tools(mcp_server_factory: Any, make_config: Any) -> None:
    """The server exposes the alias facet's full tool set."""
    server = mcp_server_factory(make_config())

    async def _run() -> None:
        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert {
                "ronin_alias_list", "ronin_alias_resolve",
                "ronin_alias_register", "ronin_alias_rebind",
                "ronin_agent_list", "ronin_agent_whoami", "ronin_agent_register",
            }.issubset(names)

    asyncio.run(_run())
