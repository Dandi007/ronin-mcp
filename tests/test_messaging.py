"""Tests for the messaging facet (ronin_msg_* / ronin_inbox_*)."""

from __future__ import annotations

import asyncio

import pytest

from tests.conftest import _make_server


def _call(mcp, name: str, args: dict) -> dict:
    result = asyncio.run(mcp.call_tool(name, args))
    sc = result.structured_content
    if sc is not None:
        return sc if isinstance(sc, dict) else {"result": sc}
    return {"text": result.content[0].text if result.content else ""}


class TestMessagingGuardrails:
    def test_gd_msg_send_proceeds(self, fake_bus) -> None:
        mcp = _make_server(bus=fake_bus)
        out = _call(mcp, "ronin_msg_send", {
            "alias": "gd:test-alias", "payload": {"body": "hello"},
            "idempotency_key": "ik-001",
        })
        assert out.get("ok") is True
        method, path, body, as_id = fake_bus.calls[-1]
        assert path == "/v1/channels/agent:gd:test-alias/publish"
        assert body["kind"] == "agent.msg.v1"
        assert body["payload"]["body"] == "hello"
        # agent.msg.v1 envelope fields are filled by ronin-mcp.
        assert body["payload"]["from_agent_id"] == "mcp-gateway"
        assert body["payload"]["depth"] == 0
        assert body["payload"]["thread_id"].startswith("ronin-")
        assert body["payload"]["sent_at"]
        assert body["idempotency_key"] == "ik-001"

    def test_gd_msg_send_with_from_alias_resolves_agent_id(self) -> None:
        from tests.conftest import FakeBusClient

        fake = FakeBusClient(response={"agent_id": "gd:sender"})
        mcp = _make_server(bus=fake)
        out = _call(mcp, "ronin_msg_send", {
            "alias": "gd:recipient", "payload": {"body": "hi"},
            "idempotency_key": "ik-2", "from_alias": "gd:sender",
        })
        # The publish response is the canned alias record; the important
        # assertion is the envelope built on the publish call.
        assert out == {"agent_id": "gd:sender"}
        publish = [c for c in fake.calls if c[0] == "POST"][-1]
        method, path, body, as_id = publish
        assert body["payload"]["from_alias"] == "gd:sender"
        assert body["payload"]["from_agent_id"] == "gd:sender"
        assert body["payload"]["body"] == "hi"

    def test_prod_msg_send_rejected(self, fake_bus) -> None:
        mcp = _make_server(bus=fake_bus)
        out = _call(mcp, "ronin_msg_send", {
            "alias": "production-alias", "payload": {}, "idempotency_key": "ik",
        })
        assert out["code"] == "PROD_WRITE_NOT_AUTHORIZED"
        assert fake_bus.calls == []

    def test_broadcast_always_requires_prod_write(self, fake_bus) -> None:
        mcp = _make_server(bus=fake_bus)
        out = _call(mcp, "ronin_msg_broadcast", {
            "payload": {}, "idempotency_key": "ik",
        })
        assert out["code"] == "PROD_WRITE_NOT_AUTHORIZED"

    def test_broadcast_rejected_even_with_gd(self, fake_bus) -> None:
        mcp = _make_server(bus=fake_bus)
        out = _call(mcp, "ronin_msg_broadcast", {
            "payload": {}, "idempotency_key": "ik",
        })
        assert out["code"] == "PROD_WRITE_NOT_AUTHORIZED"
        assert fake_bus.calls == []

    def test_broadcast_allowed_with_prod_write(self, fake_bus) -> None:
        mcp = _make_server(
            bus=fake_bus, auth_state={"ephemeral": False, "prod_write_enabled": True},
        )
        out = _call(mcp, "ronin_msg_broadcast", {
            "payload": {"alert": "x"}, "idempotency_key": "ik",
        })
        assert out.get("ok") is True
        method, path, body, as_id = fake_bus.calls[-1]
        assert path == "/v1/broadcast"

    def test_inbox_consume_gd_allowed(self, fake_bus) -> None:
        mcp = _make_server(bus=fake_bus)
        out = _call(mcp, "ronin_inbox_consume", {"alias": "gd:test-alias"})
        assert out.get("ok") is True
        method, path, body, as_id = fake_bus.calls[-1]
        assert path == "/v1/channels/agent:gd:test-alias/consume"

    def test_inbox_consume_prod_rejected(self, fake_bus) -> None:
        mcp = _make_server(bus=fake_bus)
        out = _call(mcp, "ronin_inbox_consume", {"alias": "production-alias"})
        assert out["code"] == "PROD_WRITE_NOT_AUTHORIZED"


class TestInboxOps:
    def test_ack(self, fake_bus) -> None:
        mcp = _make_server(bus=fake_bus)
        out = _call(mcp, "ronin_inbox_ack", {
            "delivery_id": "del-1", "lease_token": "lt-1",
        })
        assert out.get("ok") is True
        method, path, body, as_id = fake_bus.calls[-1]
        assert path == "/v1/deliveries/del-1/ack"
        assert body == {"lease_token": "lt-1"}

    def test_nack(self, fake_bus) -> None:
        mcp = _make_server(bus=fake_bus)
        _call(mcp, "ronin_inbox_nack", {
            "delivery_id": "del-1", "lease_token": "lt-1", "reason": "bad", "retry_in_ms": 100,
        })
        method, path, body, as_id = fake_bus.calls[-1]
        assert path == "/v1/deliveries/del-1/nack"
        assert body["reason"] == "bad"
        assert body["retry_in_ms"] == 100

    def test_renew(self, fake_bus) -> None:
        mcp = _make_server(bus=fake_bus)
        _call(mcp, "ronin_inbox_renew", {
            "delivery_id": "del-1", "lease_token": "lt-1", "lease_ms": 5000,
        })
        method, path, body, as_id = fake_bus.calls[-1]
        assert path == "/v1/deliveries/del-1/renew"
        assert body["lease_ms"] == 5000


class TestMessagingRead:
    def test_msg_read(self, fake_bus) -> None:
        fake_bus._response = {"messages": []}
        mcp = _make_server(bus=fake_bus)
        _call(mcp, "ronin_msg_read", {"channel_id": "agent:gdbot", "after_seq": 5, "limit": 10})
        method, path, params, as_id = fake_bus.calls[-1]
        assert path == "/v1/channels/agent:gdbot/messages"
        assert params == {"after_seq": 5, "limit": 10}

    def test_msg_events(self, fake_bus) -> None:
        fake_bus._response = {"events": []}
        mcp = _make_server(bus=fake_bus)
        _call(mcp, "ronin_msg_events", {"after": 3, "channel_id": "agent:gdbot"})
        method, path, params, as_id = fake_bus.calls[-1]
        assert path == "/v1/events"
        assert params == {"after": 3, "limit": 100, "channel_id": "agent:gdbot"}


class TestMessagingRoundTrip:
    def test_send_consume_ack_via_real_bus(self, bus_client, bus_env) -> None:
        mcp = _make_server(
            bus=bus_client,
            auth_state={"ephemeral": True, "prod_write_enabled": False},
        )
        _call(mcp, "ronin_agent_register", {
            "agent_id": "msgbot", "display_name": "Msg Bot", "kind": "agent",
        })
        _call(mcp, "ronin_alias_register", {
            "alias": "msgalias", "kind": "named", "agent_id": "msgbot",
        })
        sent = _call(mcp, "ronin_msg_send", {
            "alias": "msgalias", "payload": {"body": "hello"}, "idempotency_key": "ik-msg-1",
        })
        assert "message_id" in sent

        consumed = _call(mcp, "ronin_inbox_consume", {
            "alias": "msgalias", "max_messages": 10, "as_agent_id": "msgbot",
        })
        deliveries = consumed["deliveries"]
        assert len(deliveries) == 1
        assert deliveries[0]["message"]["payload"]["body"] == "hello"

        did = deliveries[0]["delivery_id"]
        lt = deliveries[0]["lease_token"]
        acked = _call(mcp, "ronin_inbox_ack", {
            "delivery_id": did, "lease_token": lt, "as_agent_id": "msgbot",
        })
        assert acked.get("state") == "acked" or acked.get("ok") is True
