"""Pump-state filesystem reader for Ronin MCP.

Reads ``/data/ronin/runs/`` for run.json / terminal.json / rounds.jsonl.
All operations are read-only; no write permissions required.
"""

from __future__ import annotations

import json
import os
from typing import Any

from ronin_mcp.backends.agent_bus import _BackendError


class PumpStateClient:
    def __init__(self, runs_root: str) -> None:
        self._runs_root = runs_root

    def list_runs(self, *, limit: int = 50, status: str | None = None) -> dict[str, Any]:
        if not os.path.isdir(self._runs_root):
            return {"runs": []}
        names = sorted(
            (n for n in os.listdir(self._runs_root) if os.path.isdir(os.path.join(self._runs_root, n))),
            key=lambda n: _mtime_or_zero(os.path.join(self._runs_root, n)),
            reverse=True,
        )
        runs: list[dict[str, Any]] = []
        for name in names:
            if len(runs) >= limit:
                break
            run = self._read_run_json(name)
            if run is None:
                continue
            if status is not None and run.get("status") != status:
                continue
            runs.append(run)
        return {"runs": runs}

    def get_run(self, run_id: str) -> dict[str, Any]:
        run = self._read_run_json(run_id)
        if run is None:
            raise _BackendError(
                "NOT_FOUND",
                f"pump run {run_id} not found",
                http_status=404,
            )
        terminal = self._read_terminal_json(run_id)
        if terminal is not None:
            run["terminal"] = terminal
        return run

    def list_rounds(
        self,
        run_id: str,
        *,
        after_round: int | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        path = os.path.join(self._runs_root, run_id, "rounds.jsonl")
        if not os.path.isfile(path):
            raise _BackendError(
                "NOT_FOUND",
                f"rounds.jsonl for run {run_id} not found",
                http_status=404,
            )
        rounds: list[dict[str, Any]] = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rnd = entry.get("round")
                if after_round is not None and isinstance(rnd, int) and rnd <= after_round:
                    continue
                rounds.append(entry)
                if len(rounds) >= limit:
                    break
        return {"run_id": run_id, "rounds": rounds}

    def _read_run_json(self, run_id: str) -> dict[str, Any] | None:
        path = os.path.join(self._runs_root, run_id, "run.json")
        if not os.path.isfile(path):
            return None
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
        if isinstance(data, dict):
            data.setdefault("run_id", run_id)
            return data
        return None

    def _read_terminal_json(self, run_id: str) -> dict[str, Any] | None:
        path = os.path.join(self._runs_root, run_id, "terminal.json")
        if not os.path.isfile(path):
            return None
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
        return data if isinstance(data, dict) else None


def _mtime_or_zero(path: str) -> float:
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0
