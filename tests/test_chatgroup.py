"""Tests for the chatgroup facet (ronin_chatgroup_*)."""

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


class TestChatgroupGuardrails:
    def test_gd_create_proceeds_with_chatgroup_prefix(self, fake_bus) -> None:
        mcp = _make_server(bus=fake_bus)
        out = _call(mcp, "ronin_chatgroup_create", {
            "channel_id": "gd:test-group", "display_name": "Test Group",
        })
        assert out.get("ok") is True
        method, path, body, as_id = fake_bus.calls[0]
        assert path == "/v1/channels"
        assert body["channel_id"] == "chatgroup:gd:test-group"
        assert body["delivery_mode"] == "fanout"
        assert body["visibility"] == "public"
        assert body["metadata"] == {"display_name": "Test Group"}

    def test_prod_create_rejected(self, fake_bus) -> None:
        mcp = _make_server(bus=fake_bus)
        out = _call(mcp, "ronin_chatgroup_create", {"channel_id": "prod-group"})
        assert out["code"] == "PROD_WRITE_NOT_AUTHORIZED"
        assert fake_bus.calls == []

    def test_gd_add_member_subscribes(self, fake_bus) -> None:
        mcp = _make_server(bus=fake_bus)
        out = _call(mcp, "ronin_chatgroup_add_member", {
            "channel_id": "gd:test-group", "agent_id": "gd:bot",
        })
        assert out.get("ok") is True
        method, path, body, as_id = fake_bus.calls[-1]
        assert method == "POST"
        assert path == "/v1/channels/chatgroup:gd:test-group/subscribe"
        assert as_id == "gd:bot"

    def test_gd_remove_member_unsubscribes(self, fake_bus) -> None:
        mcp = _make_server(bus=fake_bus)
        out = _call(mcp, "ronin_chatgroup_remove_member", {
            "channel_id": "gd:test-group", "agent_id": "gd:bot",
        })
        assert out.get("ok") is True
        method, path, body, as_id = fake_bus.calls[-1]
        assert method == "DELETE"
        assert path == "/v1/channels/chatgroup:gd:test-group/subscribe"

    def test_gd_send_publishes(self, fake_bus) -> None:
        mcp = _make_server(bus=fake_bus)
        out = _call(mcp, "ronin_chatgroup_send", {
            "channel_id": "gd:test-group",
            "payload": {"body": "hi group"},
            "idempotency_key": "ik-002",
        })
        assert out.get("ok") is True
        method, path, body, as_id = fake_bus.calls[-1]
        assert path == "/v1/channels/chatgroup:gd:test-group/publish"
        assert body["kind"] == "message"
        assert body["payload"] == {"body": "hi group"}
        assert body["idempotency_key"] == "ik-002"

    def test_prod_send_rejected(self, fake_bus) -> None:
        mcp = _make_server(bus=fake_bus)
        out = _call(mcp, "ronin_chatgroup_send", {
            "channel_id": "prod-group", "payload": {}, "idempotency_key": "ik",
        })
        assert out["code"] == "PROD_WRITE_NOT_AUTHORIZED"


class TestChatgroupRead:
    def test_list_filters_chatgroup_prefix(self, fake_bus) -> None:
        fake_bus._response = {"channels": []}
        mcp = _make_server(bus=fake_bus)
        _call(mcp, "ronin_chatgroup_list", {})
        method, path, params, as_id = fake_bus.calls[-1]
        assert params == {"prefix": "chatgroup:"}

    def test_get_resolves_full_id(self, fake_bus) -> None:
        fake_bus._response = {"channel_id": "chatgroup:gd:x"}
        mcp = _make_server(bus=fake_bus)
        out = _call(mcp, "ronin_chatgroup_get", {"channel_id": "gd:x"})
        assert out["channel_id"] == "chatgroup:gd:x"
        method, path, params, as_id = fake_bus.calls[-1]
        assert path == "/v1/channels/chatgroup:gd:x"


class TestChatgroupRoundTrip:
    def test_create_add_send_via_real_bus(self, bus_client, bus_env) -> None:
        mcp = _make_server(
            bus=bus_client,
            auth_state={"ephemeral": True, "prod_write_enabled": False},
        )
        _call(mcp, "ronin_agent_register", {
            "agent_id": "cgmember", "display_name": "Member", "kind": "agent",
        })
        created = _call(mcp, "ronin_chatgroup_create", {
            "channel_id": "cgtest", "display_name": "Test",
            "members": ["cgmember"],
        })
        assert created["channel_id"] == "chatgroup:cgtest"

        added = _call(mcp, "ronin_chatgroup_add_member", {
            "channel_id": "cgtest", "agent_id": "cgmember",
        })
        assert "cursor_seq" in added or added.get("ok") is True or "channel_id" in added

        sent = _call(mcp, "ronin_chatgroup_send", {
            "channel_id": "cgtest", "payload": {"body": "hi"}, "idempotency_key": "ik-cg-1",
        })
        assert "message_id" in sent

        lst = _call(mcp, "ronin_chatgroup_list", {})
        ids = [c["channel_id"] for c in lst["channels"]]
        assert "chatgroup:cgtest" in ids
