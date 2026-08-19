"""Tests for the alias facet (ronin_alias_* / ronin_agent_*)."""

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


class TestAliasGuardrails:
    def test_gd_alias_register_proceeds(self, fake_bus) -> None:
        mcp = _make_server(bus=fake_bus)
        out = _call(mcp, "ronin_alias_register", {
            "alias": "gd:test-alias", "kind": "named", "agent_id": "gd:test-bot",
        })
        assert out.get("ok") is True
        assert fake_bus.calls
        method, path, body, as_id = fake_bus.calls[-1]
        assert method == "POST"
        assert path == "/v1/aliases"
        assert body == {"alias": "gd:test-alias", "kind": "named", "agent_id": "gd:test-bot"}

    def test_prod_alias_register_rejected(self, fake_bus) -> None:
        mcp = _make_server(bus=fake_bus)
        out = _call(mcp, "ronin_alias_register", {
            "alias": "production-alias", "kind": "named", "agent_id": "prod-bot",
        })
        assert out["code"] == "PROD_WRITE_NOT_AUTHORIZED"
        assert fake_bus.calls == []

    def test_prod_alias_register_allowed_with_prod_write(self, fake_bus) -> None:
        mcp = _make_server(
            bus=fake_bus,
            auth_state={"ephemeral": False, "prod_write_enabled": True},
        )
        out = _call(mcp, "ronin_alias_register", {
            "alias": "production-alias", "kind": "named", "agent_id": "prod-bot",
        })
        assert out.get("ok") is True
        assert fake_bus.calls

    def test_gd_agent_register_strips_token(self, fake_bus) -> None:
        fake_bus._response = {"agent_id": "gd:test-bot", "token": "secret", "ok": True}
        mcp = _make_server(bus=fake_bus)
        out = _call(mcp, "ronin_agent_register", {
            "agent_id": "gd:test-bot", "display_name": "Test Bot", "kind": "agent",
        })
        assert "token" not in out
        assert out["agent_id"] == "gd:test-bot"

    def test_prod_agent_register_rejected(self, fake_bus) -> None:
        mcp = _make_server(bus=fake_bus)
        out = _call(mcp, "ronin_agent_register", {
            "agent_id": "prod-bot", "display_name": "Prod", "kind": "agent",
        })
        assert out["code"] == "PROD_WRITE_NOT_AUTHORIZED"
        assert fake_bus.calls == []

    def test_ephemeral_allows_prod_agent_register(self, fake_bus) -> None:
        mcp = _make_server(
            bus=fake_bus,
            auth_state={"ephemeral": True, "prod_write_enabled": False},
        )
        out = _call(mcp, "ronin_agent_register", {
            "agent_id": "prod-bot", "display_name": "Prod", "kind": "agent",
        })
        assert out.get("ok") is True


class TestAliasReadTools:
    def test_alias_list(self, fake_bus) -> None:
        fake_bus._response = {"aliases": [{"alias": "gd:x", "agent_id": "gd:bot"}]}
        mcp = _make_server(bus=fake_bus)
        out = _call(mcp, "ronin_alias_list", {"kind": "named"})
        assert "aliases" in out
        method, path, params, as_id = fake_bus.calls[-1]
        assert method == "GET" and path == "/v1/aliases"
        assert params == {"kind": "named"}

    def test_alias_resolve(self, fake_bus) -> None:
        fake_bus._response = {"alias": "gd:x", "agent_id": "gd:bot"}
        mcp = _make_server(bus=fake_bus)
        out = _call(mcp, "ronin_alias_resolve", {"alias": "gd:x"})
        assert out["agent_id"] == "gd:bot"
        method, path, params, as_id = fake_bus.calls[-1]
        assert path == "/v1/aliases/gd:x"

    def test_agent_list(self, fake_bus) -> None:
        fake_bus._response = {"agents": []}
        mcp = _make_server(bus=fake_bus)
        _call(mcp, "ronin_agent_list", {})
        method, path, params, as_id = fake_bus.calls[-1]
        assert path == "/v1/agents"

    def test_agent_whoami(self, fake_bus) -> None:
        fake_bus._response = {"agent_id": "mcp-gateway", "is_admin": False}
        mcp = _make_server(bus=fake_bus)
        out = _call(mcp, "ronin_agent_whoami", {})
        assert out["agent_id"] == "mcp-gateway"
        method, path, params, as_id = fake_bus.calls[-1]
        assert path == "/v1/agents/whoami"

    def test_alias_rebind_gd(self, fake_bus) -> None:
        mcp = _make_server(bus=fake_bus)
        out = _call(mcp, "ronin_alias_rebind", {
            "alias": "gd:x", "agent_id": "gd:bot2",
            "expected_current_agent_id": "gd:bot",
        })
        assert out.get("ok") is True
        method, path, body, as_id = fake_bus.calls[-1]
        assert path == "/v1/aliases/gd:x/rebind"
        assert body == {"agent_id": "gd:bot2", "expected_current_agent_id": "gd:bot"}

    def test_delegation_header_passed(self, fake_bus) -> None:
        mcp = _make_server(bus=fake_bus)
        _call(mcp, "ronin_agent_whoami", {"as_agent_id": "gd:alice"})
        method, path, params, as_id = fake_bus.calls[-1]
        assert as_id == "gd:alice"


class TestAliasRoundTrip:
    def test_register_list_resolve_via_real_bus(self, bus_client, bus_env) -> None:
        mcp = _make_server(
            bus=bus_client,
            auth_state={"ephemeral": True, "prod_write_enabled": False},
        )
        reg = _call(mcp, "ronin_agent_register", {
            "agent_id": "gdbot", "display_name": "GD Bot", "kind": "agent",
        })
        assert reg["agent_id"] == "gdbot"
        assert "token" not in reg

        lst = _call(mcp, "ronin_agent_list", {})
        agent_ids = [a["agent_id"] for a in lst["agents"]]
        assert "gdbot" in agent_ids

        alias = _call(mcp, "ronin_alias_register", {
            "alias": "gdalias", "kind": "named", "agent_id": "gdbot",
        })
        assert alias["alias"] == "gdalias"

        resolved = _call(mcp, "ronin_alias_resolve", {"alias": "gdalias"})
        assert resolved["current_agent_id"] == "gdbot"
