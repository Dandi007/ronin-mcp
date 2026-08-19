"""Tests for the pump-state facet (ronin_pump_*)."""

from __future__ import annotations

import asyncio

import pytest

from ronin_mcp.backends.pump_state import PumpStateClient
from tests.conftest import _make_server


def _call(mcp, name: str, args: dict) -> dict:
    result = asyncio.run(mcp.call_tool(name, args))
    sc = result.structured_content
    if sc is not None:
        return sc if isinstance(sc, dict) else {"result": sc}
    return {"text": result.content[0].text if result.content else ""}


class TestPumpState:
    def test_list_returns_runs(self, pump_root) -> None:
        root, _ = pump_root
        pump = PumpStateClient(root)
        mcp = _make_server(pump=pump)
        out = _call(mcp, "ronin_pump_list", {"limit": 10})
        ids = [r["run_id"] for r in out["runs"]]
        assert "run-aaa" in ids
        assert "run-bbb" in ids

    def test_list_status_filter(self, pump_root) -> None:
        root, _ = pump_root
        pump = PumpStateClient(root)
        mcp = _make_server(pump=pump)
        out = _call(mcp, "ronin_pump_list", {"status": "terminal"})
        ids = [r["run_id"] for r in out["runs"]]
        assert ids == ["run-bbb"]

    def test_get_includes_route_attempts(self, pump_root) -> None:
        root, _ = pump_root
        pump = PumpStateClient(root)
        mcp = _make_server(pump=pump)
        out = _call(mcp, "ronin_pump_get", {"run_id": "run-aaa"})
        assert out["run_id"] == "run-aaa"
        assert out["route_attempts"] == 2
        assert "terminal" not in out

    def test_get_includes_terminal(self, pump_root) -> None:
        root, _ = pump_root
        pump = PumpStateClient(root)
        mcp = _make_server(pump=pump)
        out = _call(mcp, "ronin_pump_get", {"run_id": "run-bbb"})
        assert out["terminal"] == {"reason": "complete", "exit_code": 0}

    def test_rounds(self, pump_root) -> None:
        root, _ = pump_root
        pump = PumpStateClient(root)
        mcp = _make_server(pump=pump)
        out = _call(mcp, "ronin_pump_rounds", {"run_id": "run-aaa"})
        assert len(out["rounds"]) == 3
        assert out["rounds"][0]["round"] == 1
        assert out["rounds"][2]["event"] == "done"

    def test_rounds_after_round(self, pump_root) -> None:
        root, _ = pump_root
        pump = PumpStateClient(root)
        mcp = _make_server(pump=pump)
        out = _call(mcp, "ronin_pump_rounds", {"run_id": "run-aaa", "after_round": 1})
        rnds = [r["round"] for r in out["rounds"]]
        assert rnds == [2, 3]

    def test_get_missing_run(self, pump_root) -> None:
        root, _ = pump_root
        pump = PumpStateClient(root)
        mcp = _make_server(pump=pump)
        out = _call(mcp, "ronin_pump_get", {"run_id": "nope"})
        assert out["code"] == "NOT_FOUND"

    def test_list_empty_root(self, tmp_path) -> None:
        pump = PumpStateClient(str(tmp_path / "nope"))
        mcp = _make_server(pump=pump)
        out = _call(mcp, "ronin_pump_list", {})
        assert out == {"runs": []}
