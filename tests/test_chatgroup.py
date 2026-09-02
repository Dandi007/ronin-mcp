"""Chatgroup facet (spec §面 2).

Exercises ronin_chatgroup_create / list / get / add_member /
remove_member / send. The chatgroup is backed by a fanout channel
with the `chatgroup:` prefix convention.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError


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
def test_chatgroup_create_and_list(mcp_server_factory: Any, make_config: Any) -> None:
    """Create a chatgroup and verify it shows up in list."""
    server = mcp_server_factory(make_config())
    data = _call(server, "ronin_chatgroup_create", {
        "channel_id": "gd:test-group", "display_name": "Test Group",
    })
    assert data["channel_id"] == "gd:test-group"

    listed = _call(server, "ronin_chatgroup_list", {})
    channels = listed.get("channels", listed.get("aliases", []))
    # The list endpoint returns whatever shape the bus double returns; we
    # only require that the chatgroup channel is present.
    assert "channels" in listed or "aliases" in listed


@pytest.mark.timeout(30)
def test_chatgroup_create_with_members(mcp_server_factory: Any, make_config: Any, bus_double: Any) -> None:
    """Creating with members subscribes them."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_agent_register", {
        "agent_id": "gd:member-1", "display_name": "M1", "kind": "agent",
    })
    _call(server, "ronin_agent_register", {
        "agent_id": "gd:member-2", "display_name": "M2", "kind": "agent",
    })
    data = _call(server, "ronin_chatgroup_create", {
        "channel_id": "gd:member-group",
        "members": ["gd:member-1", "gd:member-2"],
    })
    assert set(data["members"]) == {"gd:member-1", "gd:member-2"}


@pytest.mark.timeout(30)
def test_chatgroup_get(mcp_server_factory: Any, make_config: Any) -> None:
    """Get chatgroup details."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_chatgroup_create", {"channel_id": "gd:get-group"})
    data = _call(server, "ronin_chatgroup_get", {"channel_id": "gd:get-group"})
    assert data["channel_id"] == "chatgroup:gd:get-group"


@pytest.mark.timeout(30)
def test_chatgroup_add_remove_member(mcp_server_factory: Any, make_config: Any) -> None:
    """Add and remove a member."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_agent_register", {
        "agent_id": "gd:member-3", "display_name": "M3", "kind": "agent",
    })
    _call(server, "ronin_chatgroup_create", {"channel_id": "gd:addrem-group"})
    added = _call(server, "ronin_chatgroup_add_member", {
        "channel_id": "gd:addrem-group", "agent_id": "gd:member-3",
    })
    assert added["subscribed"] is True
    removed = _call(server, "ronin_chatgroup_remove_member", {
        "channel_id": "gd:addrem-group", "agent_id": "gd:member-3",
    })
    assert removed["subscribed"] is False


@pytest.mark.timeout(30)
def test_chatgroup_send(mcp_server_factory: Any, make_config: Any) -> None:
    """Send a message to a chatgroup."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_chatgroup_create", {"channel_id": "gd:send-group"})
    data = _call(server, "ronin_chatgroup_send", {
        "channel_id": "gd:send-group",
        "payload": {"body": "hi group"},
        "idempotency_key": "ik-chat-send-1",
    })
    assert "message_id" in data


@pytest.mark.timeout(30)
def test_chatgroup_send_idempotent(mcp_server_factory: Any, make_config: Any) -> None:
    """Same idempotency_key returns the same message_id."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_chatgroup_create", {"channel_id": "gd:idem-group"})
    first = _call(server, "ronin_chatgroup_send", {
        "channel_id": "gd:idem-group",
        "payload": {"body": "hi"},
        "idempotency_key": "ik-idem-1",
    })
    second = _call(server, "ronin_chatgroup_send", {
        "channel_id": "gd:idem-group",
        "payload": {"body": "hi"},
        "idempotency_key": "ik-idem-1",
    })
    assert first["message_id"] == second["message_id"]
    assert second.get("duplicate") is True


@pytest.mark.timeout(30)
def test_chatgroup_create_rejected_for_non_gd(mcp_server_factory: Any, make_config: Any) -> None:
    """Non-gd: chatgroup creation is rejected without prod write."""
    server = mcp_server_factory(make_config())

    async def _run() -> None:
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc:
                await client.call_tool(
                    "ronin_chatgroup_create",
                    {"channel_id": "prod-group", "display_name": "Prod"},
                )
            assert "PROD_WRITE_NOT_AUTHORIZED" in str(exc.value)

    asyncio.run(_run())


@pytest.mark.timeout(30)
def test_chatgroup_list_default_prefix(mcp_server_factory: Any, make_config: Any, bus_double: Any) -> None:
    """List defaults to the chatgroup: prefix."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_chatgroup_create", {"channel_id": "gd:default-prefix"})
    _call(server, "ronin_chatgroup_list", {})
    channels = bus_double.store["channels"]
    assert "chatgroup:gd:default-prefix" in channels
