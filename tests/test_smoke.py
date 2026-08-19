"""Spec smoke-loop acceptance (spec §冒烟闭环).

Items 1-13 require live backends; we run the alias/chatgroup/messaging
round-trip against an ephemeral agent-bus. Items 14-15 verify the write
guardrails at the ronin-mcp entrance.
"""

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


@pytest.fixture
def ephemeral_mcp(bus_client):
    return _make_server(
        bus=bus_client,
        auth_state={"ephemeral": True, "prod_write_enabled": False},
    )


class TestSmokeRoundTrip:
    def test_alias_agent_lifecycle(self, ephemeral_mcp) -> None:
        mcp = ephemeral_mcp
        reg = _call(mcp, "ronin_agent_register", {
            "agent_id": "smokebot", "display_name": "Smoke Bot",
        })
        assert reg["agent_id"] == "smokebot"
        assert "token" not in reg

        lst = _call(mcp, "ronin_agent_list", {})
        assert "smokebot" in [a["agent_id"] for a in lst["agents"]]

        alias = _call(mcp, "ronin_alias_register", {
            "alias": "smokealias", "kind": "named", "agent_id": "smokebot",
        })
        assert alias["alias"] == "smokealias"

        resolved = _call(mcp, "ronin_alias_resolve", {"alias": "smokealias"})
        assert resolved["current_agent_id"] == "smokebot"

    def test_msg_send_consume(self, ephemeral_mcp) -> None:
        mcp = ephemeral_mcp
        _call(mcp, "ronin_agent_register", {"agent_id": "msgbot", "display_name": "M"})
        _call(mcp, "ronin_alias_register", {
            "alias": "msgalias", "kind": "named", "agent_id": "msgbot",
        })
        sent = _call(mcp, "ronin_msg_send", {
            "alias": "msgalias", "payload": {"body": "hello"}, "idempotency_key": "smoke-1",
        })
        assert "message_id" in sent

        # Consume on behalf of the inbox owner (msgbot); the gateway cannot
        # consume a private inbox without delegation.
        consumed = _call(mcp, "ronin_inbox_consume", {
            "alias": "msgalias", "as_agent_id": "msgbot",
        })
        assert len(consumed["deliveries"]) == 1
        assert consumed["deliveries"][0]["message"]["payload"]["body"] == "hello"

    def test_chatgroup_lifecycle(self, ephemeral_mcp) -> None:
        mcp = ephemeral_mcp
        _call(mcp, "ronin_agent_register", {"agent_id": "cgm", "display_name": "C"})
        created = _call(mcp, "ronin_chatgroup_create", {
            "channel_id": "smokegroup", "display_name": "Smoke Group",
            "members": ["cgm"],
        })
        assert created["channel_id"] == "chatgroup:smokegroup"

        added = _call(mcp, "ronin_chatgroup_add_member", {
            "channel_id": "smokegroup", "agent_id": "cgm",
        })
        assert "cursor_seq" in added or added.get("ok") is True or "channel_id" in added

        sent = _call(mcp, "ronin_chatgroup_send", {
            "channel_id": "smokegroup", "payload": {"body": "hi"}, "idempotency_key": "smoke-2",
        })
        assert "message_id" in sent


class TestSmokeGuardrails:
    def test_prod_alias_register_returns_403_shape(self, fake_bus) -> None:
        mcp = _make_server(bus=fake_bus)
        out = _call(mcp, "ronin_alias_register", {
            "alias": "production-alias", "kind": "named", "agent_id": "prodbot",
        })
        assert out == {
            "code": "PROD_WRITE_NOT_AUTHORIZED",
            "message": (
                "Production write requires RONIN_PROD_WRITE=1 or --prod-write. "
                "Use gd: prefix for test resources."
            ),
            "details": {"retryable": False},
        }
        assert fake_bus.calls == []

    def test_gate_approve_returns_403_shape(self, fake_controller) -> None:
        mcp = _make_server(controller=fake_controller)
        out = _call(mcp, "ronin_gate_approve", {
            "development_id": "dev-1", "gate_id": "g1",
            "idempotency_key": "ik", "expected_revision": 1,
            "operator_identity": "op",
        })
        assert out == {
            "code": "GATE_REQUIRES_PROD_WRITE",
            "message": (
                "Gate approval requires RONIN_PROD_WRITE=1 or --prod-write. "
                "Use gd: prefix for test resources."
            ),
            "details": {"retryable": False},
        }
        assert fake_controller.calls == []
