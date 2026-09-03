"""Messaging facet (spec §面 3).

Exercises ronin_msg_send / broadcast / inbox_consume / ack / nack /
renew / msg_read / msg_events.
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
def test_msg_send_and_consume(mcp_server_factory: Any, make_config: Any) -> None:
    """Send a message to an alias and consume it from the inbox."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_agent_register", {
        "agent_id": "gd:msg-bot", "display_name": "Msg Bot", "kind": "agent",
    })
    _call(server, "ronin_alias_register", {
        "alias": "gd:msg-alias", "kind": "named", "agent_id": "gd:msg-bot",
    })
    sent = _call(server, "ronin_msg_send", {
        "alias": "gd:msg-alias",
        "payload": {"body": "hello"},
        "idempotency_key": "ik-msg-1",
    })
    assert "message_id" in sent

    consumed = _call(server, "ronin_inbox_consume", {
        "alias": "gd:msg-alias", "max_messages": 10,
    })
    deliveries = consumed["deliveries"]
    assert len(deliveries) == 1
    assert deliveries[0]["message"]["payload"]["body"] == "hello"


@pytest.mark.timeout(30)
def test_msg_send_idempotent(mcp_server_factory: Any, make_config: Any) -> None:
    """Same idempotency_key returns the same message_id."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_agent_register", {
        "agent_id": "gd:idem-bot", "display_name": "Idem", "kind": "agent",
    })
    _call(server, "ronin_alias_register", {
        "alias": "gd:idem-alias", "kind": "named", "agent_id": "gd:idem-bot",
    })
    first = _call(server, "ronin_msg_send", {
        "alias": "gd:idem-alias",
        "payload": {"body": "hi"},
        "idempotency_key": "ik-idem-msg-1",
    })
    second = _call(server, "ronin_msg_send", {
        "alias": "gd:idem-alias",
        "payload": {"body": "hi"},
        "idempotency_key": "ik-idem-msg-1",
    })
    assert first["message_id"] == second["message_id"]


@pytest.mark.timeout(30)
def test_inbox_ack(mcp_server_factory: Any, make_config: Any) -> None:
    """Consume then ack a delivery."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_agent_register", {
        "agent_id": "gd:ack-bot", "display_name": "Ack", "kind": "agent",
    })
    _call(server, "ronin_alias_register", {
        "alias": "gd:ack-alias", "kind": "named", "agent_id": "gd:ack-bot",
    })
    _call(server, "ronin_msg_send", {
        "alias": "gd:ack-alias",
        "payload": {"body": "ack-me"},
        "idempotency_key": "ik-ack-1",
    })
    consumed = _call(server, "ronin_inbox_consume", {"alias": "gd:ack-alias"})
    did = consumed["deliveries"][0]["delivery_id"]
    lt = consumed["deliveries"][0]["lease_token"]
    acked = _call(server, "ronin_inbox_ack", {
        "delivery_id": did, "lease_token": lt,
    })
    assert acked["state"] == "acked"


@pytest.mark.timeout(30)
def test_inbox_nack(mcp_server_factory: Any, make_config: Any) -> None:
    """Consume then nack a delivery."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_agent_register", {
        "agent_id": "gd:nack-bot", "display_name": "Nack", "kind": "agent",
    })
    _call(server, "ronin_alias_register", {
        "alias": "gd:nack-alias", "kind": "named", "agent_id": "gd:nack-bot",
    })
    _call(server, "ronin_msg_send", {
        "alias": "gd:nack-alias",
        "payload": {"body": "nack-me"},
        "idempotency_key": "ik-nack-1",
    })
    consumed = _call(server, "ronin_inbox_consume", {"alias": "gd:nack-alias"})
    did = consumed["deliveries"][0]["delivery_id"]
    lt = consumed["deliveries"][0]["lease_token"]
    nacked = _call(server, "ronin_inbox_nack", {
        "delivery_id": did, "lease_token": lt, "reason": "bad",
    })
    assert nacked["state"] == "nacked"


@pytest.mark.timeout(30)
def test_inbox_renew(mcp_server_factory: Any, make_config: Any) -> None:
    """Consume then renew a lease."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_agent_register", {
        "agent_id": "gd:renew-bot", "display_name": "Renew", "kind": "agent",
    })
    _call(server, "ronin_alias_register", {
        "alias": "gd:renew-alias", "kind": "named", "agent_id": "gd:renew-bot",
    })
    _call(server, "ronin_msg_send", {
        "alias": "gd:renew-alias",
        "payload": {"body": "renew-me"},
        "idempotency_key": "ik-renew-1",
    })
    consumed = _call(server, "ronin_inbox_consume", {"alias": "gd:renew-alias"})
    did = consumed["deliveries"][0]["delivery_id"]
    lt = consumed["deliveries"][0]["lease_token"]
    renewed = _call(server, "ronin_inbox_renew", {
        "delivery_id": did, "lease_token": lt, "lease_ms": 60000,
    })
    assert renewed["state"] == "leased"


@pytest.mark.timeout(30)
def test_msg_read(mcp_server_factory: Any, make_config: Any) -> None:
    """Read channel message history."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_agent_register", {
        "agent_id": "gd:read-bot", "display_name": "Read", "kind": "agent",
    })
    _call(server, "ronin_alias_register", {
        "alias": "gd:read-alias", "kind": "named", "agent_id": "gd:read-bot",
    })
    _call(server, "ronin_msg_send", {
        "alias": "gd:read-alias",
        "payload": {"body": "read-me"},
        "idempotency_key": "ik-read-1",
    })
    data = _call(server, "ronin_msg_read", {"channel_id": "agent:gd:read-alias"})
    messages = data["messages"]
    assert len(messages) == 1
    assert messages[0]["payload"]["body"] == "read-me"


@pytest.mark.timeout(30)
def test_msg_events(mcp_server_factory: Any, make_config: Any) -> None:
    """Read bus event stream."""
    server = mcp_server_factory(make_config())
    _call(server, "ronin_agent_register", {
        "agent_id": "gd:ev-bot", "display_name": "Ev", "kind": "agent",
    })
    _call(server, "ronin_alias_register", {
        "alias": "gd:ev-alias", "kind": "named", "agent_id": "gd:ev-bot",
    })
    _call(server, "ronin_msg_send", {
        "alias": "gd:ev-alias",
        "payload": {"body": "ev"},
        "idempotency_key": "ik-ev-1",
    })
    data = _call(server, "ronin_msg_events", {"channel_id": "agent:gd:ev-alias"})
    events = data["events"]
    assert len(events) > 0


@pytest.mark.timeout(30)
def test_msg_send_rejected_for_non_gd(mcp_server_factory: Any, make_config: Any) -> None:
    """Non-gd: msg_send is rejected without prod write."""
    server = mcp_server_factory(make_config())

    async def _run() -> None:
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc:
                await client.call_tool("ronin_msg_send", {
                    "alias": "prod-alias",
                    "payload": {"body": "hi"},
                    "idempotency_key": "ik-prod-1",
                })
            assert "PROD_WRITE_NOT_AUTHORIZED" in str(exc.value)

    asyncio.run(_run())


@pytest.mark.timeout(30)
def test_inbox_consume_rejected_for_non_gd(mcp_server_factory: Any, make_config: Any) -> None:
    """Non-gd: inbox_consume is rejected without prod write."""
    server = mcp_server_factory(make_config())

    async def _run() -> None:
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc:
                await client.call_tool("ronin_inbox_consume", {"alias": "prod-alias"})
            assert "PROD_WRITE_NOT_AUTHORIZED" in str(exc.value)

    asyncio.run(_run())
