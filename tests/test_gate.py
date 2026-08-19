"""Tests for the gate facet (ronin_gate_*).

Gate approve/reject are B-class irreversible and ALWAYS require
RONIN_PROD_WRITE=1, even for gd: developments.
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


GATE_ARGS = {
    "development_id": "dev-1",
    "gate_id": "gate-1",
    "idempotency_key": "ik",
    "expected_revision": 2,
    "operator_identity": "operator-alice",
}


class TestGateGuardrails:
    def test_approve_rejected_without_prod_write(self, fake_controller) -> None:
        mcp = _make_server(controller=fake_controller)
        out = _call(mcp, "ronin_gate_approve", dict(GATE_ARGS))
        assert out["code"] == "GATE_REQUIRES_PROD_WRITE"
        assert fake_controller.calls == []

    def test_reject_rejected_without_prod_write(self, fake_controller) -> None:
        mcp = _make_server(controller=fake_controller)
        out = _call(mcp, "ronin_gate_reject", dict(GATE_ARGS))
        assert out["code"] == "GATE_REQUIRES_PROD_WRITE"
        assert fake_controller.calls == []

    def test_gd_gate_still_requires_prod_write(self, fake_controller) -> None:
        mcp = _make_server(controller=fake_controller)
        args = dict(GATE_ARGS)
        args["development_id"] = "gd:dev-1"
        out = _call(mcp, "ronin_gate_approve", args)
        assert out["code"] == "GATE_REQUIRES_PROD_WRITE"
        assert fake_controller.calls == []

    def test_ephemeral_allows_gate_without_prod_write(self, fake_controller) -> None:
        # Ephemeral mode is highest priority and opens the full write surface
        # (spec 判据 1 Rule 1: 无任何限制), so gate approval proceeds even
        # without prod-write — this is the test/dev escape hatch.
        mcp = _make_server(
            controller=fake_controller,
            auth_state={"ephemeral": True, "prod_write_enabled": False},
        )
        out = _call(mcp, "ronin_gate_approve", dict(GATE_ARGS))
        assert out.get("ok") is True
        assert fake_controller.calls != []


class TestGateAuthorized:
    def test_approve_with_prod_write(self, fake_controller) -> None:
        mcp = _make_server(
            controller=fake_controller,
            auth_state={"ephemeral": False, "prod_write_enabled": True},
        )
        out = _call(mcp, "ronin_gate_approve", dict(GATE_ARGS))
        assert out.get("ok") is True
        method, path, body, op = fake_controller.calls[-1]
        assert path == "/v1/developments/dev-1/commands/gate"
        assert body["decision"] == "approve"
        assert body["gate_id"] == "gate-1"
        assert body["operator_identity"] == "operator-alice"
        assert op == "operator-alice"

    def test_reject_with_prod_write(self, fake_controller) -> None:
        mcp = _make_server(
            controller=fake_controller,
            auth_state={"ephemeral": False, "prod_write_enabled": True},
        )
        out = _call(mcp, "ronin_gate_reject", dict(GATE_ARGS))
        assert out.get("ok") is True
        method, path, body, op = fake_controller.calls[-1]
        assert body["decision"] == "reject"
