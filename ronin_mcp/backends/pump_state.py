"""Pump-state filesystem backend.

Reads /data/ronin/runs/ for goal-agent pump run state. All operations
are read-only: the pump lifecycle is owned by the goal-agent, not by
ronin-mcp. The reader tolerates missing files (pump runs that haven't
written terminal.json yet) and returns a stable shape for each tool.
"""

from __future__ import annotations

import json
import os
from typing import Any


class PumpStateClient:
    """Read-only reader for /data/ronin/runs/."""

    def __init__(self, runs_root: str) -> None:
        self._runs_root = runs_root

    @property
    def runs_root(self) -> str:
        return self._runs_root

    def list_runs(self, limit: int = 50, status: str | None = None) -> dict[str, Any]:
        """List pump runs ordered newest-first by mtime.

        Each entry surfaces the run_id / folder_id / status / started_at
        / terminal_at / rounds / route_attempts fields from run.json
        when present. Runs whose run.json is missing or unreadable are
        skipped (the pump may still be initializing).
        """
        if not os.path.isdir(self._runs_root):
            return {"runs": []}

        entries: list[dict[str, Any]] = []
        for name in os.listdir(self._runs_root):
            run_dir = os.path.join(self._runs_root, name)
            if not os.path.isdir(run_dir):
                continue
            run_json = os.path.join(run_dir, "run.json")
            if not os.path.isfile(run_json):
                continue
            data = _read_json(run_json)
            if data is None:
                continue
            if status and data.get("status") != status:
                continue
            data.setdefault("run_id", name)
            data["_run_dir"] = run_dir
            entries.append(data)

        entries.sort(
            key=lambda e: os.path.getmtime(os.path.join(self._runs_root, e.get("run_id", ""))),
            reverse=True,
        )
        if limit > 0:
            entries = entries[:limit]
        for entry in entries:
            entry.pop("_run_dir", None)
        return {"runs": entries}

    def get_run(self, run_id: str) -> dict[str, Any]:
        """Return run.json merged with terminal.json (when present)."""
        run_dir = os.path.join(self._runs_root, run_id)
        run_json = os.path.join(run_dir, "run.json")
        if not os.path.isfile(run_json):
            return {"run_id": run_id, "error": "RUN_NOT_FOUND"}
        merged: dict[str, Any] = {"run_id": run_id}
        run_data = _read_json(run_json)
        if run_data:
            merged.update(run_data)
        terminal_json = os.path.join(run_dir, "terminal.json")
        if os.path.isfile(terminal_json):
            terminal = _read_json(terminal_json)
            if terminal:
                merged["terminal"] = terminal
        return merged

    def get_rounds(
        self,
        run_id: str,
        after_round: int | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Read rounds.jsonl incrementally.

        Each line is a JSON object with a `round` field (int). When
        after_round is given, only rounds strictly greater than
        after_round are returned.
        """
        rounds_path = os.path.join(self._runs_root, run_id, "rounds.jsonl")
        if not os.path.isfile(rounds_path):
            return {"run_id": run_id, "rounds": []}
        rounds: list[dict[str, Any]] = []
        with open(rounds_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except ValueError:
                    continue
                if not isinstance(entry, dict):
                    continue
                if after_round is not None:
                    r = entry.get("round")
                    if isinstance(r, int) and r <= after_round:
                        continue
                rounds.append(entry)
                if len(rounds) >= limit:
                    break
        return {"run_id": run_id, "rounds": rounds}


def _read_json(path: str) -> dict[str, Any] | None:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (ValueError, OSError):
        return None
