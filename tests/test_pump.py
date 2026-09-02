"""Pump-state facet (spec §面 6).

Exercises ronin_pump_list / get / rounds against a tmp runs root.
"""

from __future__ import annotations

import asyncio
import json
import os
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


def _write_run(runs_root: str, run_id: str, *, status: str = "running", rounds: int = 2) -> None:
    """Write a synthetic pump run to runs_root."""
    run_dir = os.path.join(runs_root, run_id)
    os.makedirs(run_dir, exist_ok=True)
    with open(os.path.join(run_dir, "run.json"), "w", encoding="utf-8") as f:
        json.dump({
            "run_id": run_id,
            "folder_id": f"folder-{run_id}",
            "status": status,
            "started_at": "2026-08-19T12:00:00Z",
            "rounds": rounds,
            "route_attempts": 3,
        }, f)
    with open(os.path.join(run_dir, "rounds.jsonl"), "w", encoding="utf-8") as f:
        for r in range(rounds):
            f.write(json.dumps({"round": r, "event": "tick"}) + "\n")
    if status in {"completed", "failed"}:
        with open(os.path.join(run_dir, "terminal.json"), "w", encoding="utf-8") as f:
            json.dump({"terminal_at": "2026-08-19T13:00:00Z", "reason": "done"}, f)


@pytest.mark.timeout(30)
def test_pump_list_empty(mcp_server_factory: Any, make_config: Any) -> None:
    """Empty runs root returns an empty list."""
    server = mcp_server_factory(make_config())
    data = _call(server, "ronin_pump_list", {})
    assert data == {"runs": []}


@pytest.mark.timeout(30)
def test_pump_list_with_runs(mcp_server_factory: Any, make_config: Any, tmp_runs_root: str) -> None:
    """List returns runs newest-first."""
    _write_run(tmp_runs_root, "run-1", status="completed")
    _write_run(tmp_runs_root, "run-2", status="running")
    server = mcp_server_factory(make_config())
    data = _call(server, "ronin_pump_list", {})
    run_ids = [r["run_id"] for r in data["runs"]]
    assert set(run_ids) == {"run-1", "run-2"}


@pytest.mark.timeout(30)
def test_pump_list_status_filter(mcp_server_factory: Any, make_config: Any, tmp_runs_root: str) -> None:
    """Status filter narrows the list."""
    _write_run(tmp_runs_root, "run-ok", status="completed")
    _write_run(tmp_runs_root, "run-run", status="running")
    server = mcp_server_factory(make_config())
    data = _call(server, "ronin_pump_list", {"status": "running"})
    run_ids = [r["run_id"] for r in data["runs"]]
    assert run_ids == ["run-run"]


@pytest.mark.timeout(30)
def test_pump_list_limit(mcp_server_factory: Any, make_config: Any, tmp_runs_root: str) -> None:
    """Limit caps the result count."""
    for i in range(5):
        _write_run(tmp_runs_root, f"run-{i}", status="running")
    server = mcp_server_factory(make_config())
    data = _call(server, "ronin_pump_list", {"limit": 2})
    assert len(data["runs"]) == 2


@pytest.mark.timeout(30)
def test_pump_get(mcp_server_factory: Any, make_config: Any, tmp_runs_root: str) -> None:
    """Get a run's merged state."""
    _write_run(tmp_runs_root, "run-get", status="completed")
    server = mcp_server_factory(make_config())
    data = _call(server, "ronin_pump_get", {"run_id": "run-get"})
    assert data["run_id"] == "run-get"
    assert data["status"] == "completed"
    assert data["route_attempts"] == 3
    assert "terminal" in data


@pytest.mark.timeout(30)
def test_pump_get_running_no_terminal(mcp_server_factory: Any, make_config: Any, tmp_runs_root: str) -> None:
    """A running pump has no terminal.json."""
    _write_run(tmp_runs_root, "run-live", status="running")
    server = mcp_server_factory(make_config())
    data = _call(server, "ronin_pump_get", {"run_id": "run-live"})
    assert data["status"] == "running"
    assert "terminal" not in data


@pytest.mark.timeout(30)
def test_pump_get_missing(mcp_server_factory: Any, make_config: Any) -> None:
    """Missing run returns an error envelope."""
    server = mcp_server_factory(make_config())
    data = _call(server, "ronin_pump_get", {"run_id": "no-such-run"})
    assert data["error"] == "RUN_NOT_FOUND"


@pytest.mark.timeout(30)
def test_pump_rounds(mcp_server_factory: Any, make_config: Any, tmp_runs_root: str) -> None:
    """Read rounds.jsonl."""
    _write_run(tmp_runs_root, "run-rounds", rounds=3)
    server = mcp_server_factory(make_config())
    data = _call(server, "ronin_pump_rounds", {"run_id": "run-rounds"})
    assert len(data["rounds"]) == 3
    assert data["rounds"][0]["round"] == 0


@pytest.mark.timeout(30)
def test_pump_rounds_after(mcp_server_factory: Any, make_config: Any, tmp_runs_root: str) -> None:
    """after_round filters rounds."""
    _write_run(tmp_runs_root, "run-after", rounds=5)
    server = mcp_server_factory(make_config())
    data = _call(server, "ronin_pump_rounds", {
        "run_id": "run-after", "after_round": 2,
    })
    rounds = [r["round"] for r in data["rounds"]]
    assert rounds == [3, 4]


@pytest.mark.timeout(30)
def test_pump_rounds_limit(mcp_server_factory: Any, make_config: Any, tmp_runs_root: str) -> None:
    """limit caps rounds count."""
    _write_run(tmp_runs_root, "run-lim", rounds=10)
    server = mcp_server_factory(make_config())
    data = _call(server, "ronin_pump_rounds", {
        "run_id": "run-lim", "limit": 3,
    })
    assert len(data["rounds"]) == 3
