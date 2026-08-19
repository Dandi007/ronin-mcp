"""Tests for the development facet (ronin_dev_*)."""

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


class TestDevGuardrails:
    def test_gd_create_proceeds(self, fake_controller) -> None:
        mcp = _make_server(controller=fake_controller)
        out = _call(mcp, "ronin_dev_create", {
            "name": "gd:dev-1", "goal": "g", "idempotency_key": "ik",
            "reason": "r", "initial_handoff": {"k": "v"},
        })
        assert out.get("ok") is True
        method, path, body, op = fake_controller.calls[-1]
        assert path == "/v1/developments"
        assert body["name"] == "gd:dev-1"
        assert body["initial_handoff"] == {"k": "v"}

    def test_prod_create_rejected(self, fake_controller) -> None:
        mcp = _make_server(controller=fake_controller)
        out = _call(mcp, "ronin_dev_create", {
            "name": "production-dev", "goal": "g", "idempotency_key": "ik",
            "reason": "r", "initial_handoff": {},
        })
        assert out["code"] == "PROD_WRITE_NOT_AUTHORIZED"
        assert fake_controller.calls == []

    def test_prod_create_allowed_with_prod_write(self, fake_controller) -> None:
        mcp = _make_server(
            controller=fake_controller,
            auth_state={"ephemeral": False, "prod_write_enabled": True},
        )
        out = _call(mcp, "ronin_dev_create", {
            "name": "production-dev", "goal": "g", "idempotency_key": "ik",
            "reason": "r", "initial_handoff": {},
        })
        assert out.get("ok") is True


class TestDevReadTools:
    def test_dev_list(self, fake_controller) -> None:
        fake_controller._response = {"developments": []}
        mcp = _make_server(controller=fake_controller)
        _call(mcp, "ronin_dev_list", {"state": "IMPLEMENTING", "limit": 5})
        method, path, params, op = fake_controller.calls[-1]
        assert path == "/v1/developments"
        assert params == {"limit": 5, "state": "IMPLEMENTING"}

    def test_dev_get(self, fake_controller) -> None:
        mcp = _make_server(controller=fake_controller)
        _call(mcp, "ronin_dev_get", {"development_id": "dev-1"})
        method, path, params, op = fake_controller.calls[-1]
        assert path == "/v1/developments/dev-1"

    def test_dev_events(self, fake_controller) -> None:
        mcp = _make_server(controller=fake_controller)
        _call(mcp, "ronin_dev_events", {"development_id": "dev-1", "after": "evt-2"})
        method, path, params, op = fake_controller.calls[-1]
        assert path == "/v1/developments/dev-1/events"
        assert params == {"limit": 100, "after": "evt-2"}

    def test_dev_evidence(self, fake_controller) -> None:
        mcp = _make_server(controller=fake_controller)
        _call(mcp, "ronin_dev_evidence", {"development_id": "dev-1"})
        method, path, params, op = fake_controller.calls[-1]
        assert path == "/v1/developments/dev-1/evidence"


class TestDevWriteTools:
    def test_dev_start(self, fake_controller) -> None:
        mcp = _make_server(controller=fake_controller)
        _call(mcp, "ronin_dev_start", {
            "development_id": "gd:dev-1", "idempotency_key": "ik",
            "expected_revision": 3, "reason": "go",
        })
        method, path, body, op = fake_controller.calls[-1]
        assert path == "/v1/developments/gd:dev-1/commands/start"
        assert body["expected_revision"] == 3
        assert body["reason"] == "go"

    def test_dev_steer(self, fake_controller) -> None:
        mcp = _make_server(controller=fake_controller)
        _call(mcp, "ronin_dev_steer", {
            "development_id": "gd:dev-1", "instruction": "stop", "idempotency_key": "ik",
            "expected_revision": 4,
        })
        method, path, body, op = fake_controller.calls[-1]
        assert path == "/v1/developments/gd:dev-1/commands/steer"
        assert body["instruction"] == "stop"
        assert body["urgency"] == "next_safe_boundary"

    def test_dev_reconfigure(self, fake_controller) -> None:
        mcp = _make_server(controller=fake_controller)
        _call(mcp, "ronin_dev_reconfigure", {
            "development_id": "gd:dev-1", "idempotency_key": "ik",
            "expected_revision": 4, "profile": "alt",
        })
        method, path, body, op = fake_controller.calls[-1]
        assert path == "/v1/developments/gd:dev-1/commands/reconfigure"
        assert body["profile"] == "alt"

    def test_dev_control(self, fake_controller) -> None:
        mcp = _make_server(controller=fake_controller)
        _call(mcp, "ronin_dev_control", {
            "development_id": "gd:dev-1", "action": "pause", "idempotency_key": "ik",
            "expected_revision": 4,
        })
        method, path, body, op = fake_controller.calls[-1]
        assert path == "/v1/developments/gd:dev-1/commands/control"
        assert body["action"] == "pause"

    def test_dev_relock(self, fake_controller) -> None:
        mcp = _make_server(controller=fake_controller)
        _call(mcp, "ronin_dev_relock", {
            "development_id": "gd:dev-1", "plugin_commit": "abc123",
            "idempotency_key": "ik", "expected_revision": 4,
        })
        method, path, body, op = fake_controller.calls[-1]
        assert path == "/v1/developments/gd:dev-1/commands/relock"
        assert body["plugin_commit"] == "abc123"


class TestDevWriteGuardrails:
    """Spec 判据 1: *_start / *_steer / *_control / *_reconfigure / *_relock
    are write-surface tools and must run check_write_auth at the entrance."""

    @pytest.mark.parametrize(
        "tool,args",
        [
            ("ronin_dev_start", {"development_id": "prod-dev", "idempotency_key": "ik",
                                 "expected_revision": 3, "reason": "go"}),
            ("ronin_dev_steer", {"development_id": "prod-dev", "instruction": "stop",
                                 "idempotency_key": "ik", "expected_revision": 4}),
            ("ronin_dev_reconfigure", {"development_id": "prod-dev", "idempotency_key": "ik",
                                       "expected_revision": 4, "profile": "alt"}),
            ("ronin_dev_control", {"development_id": "prod-dev", "action": "pause",
                                   "idempotency_key": "ik", "expected_revision": 4}),
            ("ronin_dev_relock", {"development_id": "prod-dev", "plugin_commit": "abc123",
                                  "idempotency_key": "ik", "expected_revision": 4}),
        ],
    )
    def test_prod_dev_command_rejected(self, fake_controller, tool, args) -> None:
        mcp = _make_server(controller=fake_controller)
        out = _call(mcp, tool, args)
        assert out["code"] == "PROD_WRITE_NOT_AUTHORIZED"
        assert fake_controller.calls == []

    @pytest.mark.parametrize(
        "tool,extra",
        [
            ("ronin_dev_start", {"reason": "go"}),
            ("ronin_dev_steer", {"instruction": "stop"}),
            ("ronin_dev_reconfigure", {"profile": "alt"}),
            ("ronin_dev_control", {"action": "pause"}),
            ("ronin_dev_relock", {"plugin_commit": "abc123"}),
        ],
    )
    def test_gd_dev_command_proceeds(self, fake_controller, tool, extra) -> None:
        mcp = _make_server(controller=fake_controller)
        args = {"development_id": "gd:dev-1", "idempotency_key": "ik",
                "expected_revision": 4}
        args.update(extra)
        out = _call(mcp, tool, args)
        assert out.get("ok") is True
        assert fake_controller.calls != []

    @pytest.mark.parametrize(
        "tool,extra",
        [
            ("ronin_dev_start", {"reason": "go"}),
            ("ronin_dev_steer", {"instruction": "stop"}),
            ("ronin_dev_reconfigure", {"profile": "alt"}),
            ("ronin_dev_control", {"action": "pause"}),
            ("ronin_dev_relock", {"plugin_commit": "abc123"}),
        ],
    )
    def test_prod_dev_command_allowed_with_prod_write(
        self, fake_controller, tool, extra
    ) -> None:
        mcp = _make_server(
            controller=fake_controller,
            auth_state={"ephemeral": False, "prod_write_enabled": True},
        )
        args = {"development_id": "prod-dev", "idempotency_key": "ik",
                "expected_revision": 4}
        args.update(extra)
        out = _call(mcp, tool, args)
        assert out.get("ok") is True
        assert fake_controller.calls != []
