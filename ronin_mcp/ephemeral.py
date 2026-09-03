"""Ephemeral runtime: temporary agent-bus + work-folder dir.

Spec 判据 1 rule 1 + 判据 3 require ``--ephemeral`` to:

1. Start a temporary agent-bus instance (agent-bus itself supports
   ``--ephemeral``) and route all agent-bus writes to it.
2. Route all work-folder writes to a temporary directory.
3. Clean up every temporary resource on process exit.

``EphemeralRuntime`` owns those resources and exposes the URL / token
the server needs to wire its agent-bus client at the ephemeral backend
instead of the configured (potentially production) backend URL. The
spawners are injectable so tests can boot in-process doubles instead of
subprocesses; the default spawner launches the real agent-bus as a
subprocess.
"""

from __future__ import annotations

import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Optional

# Public type alias for the injectable bus spawner.
BusSpawner = Callable[[], "tuple[str, str, Callable[[], None]]"]


class EphemeralRuntime:
    """Owns temporary agent-bus + work-folder resources.

    ``start()`` boots the ephemeral agent-bus; ``close()`` tears it
    down and removes the temp work-folder root. ``close()`` is
    idempotent and registered with ``atexit`` so the cleanup runs even
    if the server is killed by a signal that bypasses the normal
    shutdown path.
    """

    def __init__(
        self,
        *,
        bus_spawner: BusSpawner | None = None,
        work_folder_root: str | None = None,
    ) -> None:
        self._bus_spawner = bus_spawner or default_bus_spawner
        self._work_folder_root: str | None = work_folder_root
        self._owns_wf_root = work_folder_root is None
        self._bus_url = ""
        self._bus_gateway_token = ""
        self._cleanups: list[Callable[[], None]] = []
        self._started = False
        self._closed = False
        self._atexit_registered = False

    @property
    def bus_url(self) -> str:
        return self._bus_url

    @property
    def bus_gateway_token(self) -> str:
        return self._bus_gateway_token

    @property
    def work_folder_root(self) -> str:
        if self._work_folder_root is None:
            self._work_folder_root = tempfile.mkdtemp(prefix="ronin-wf-ephemeral-")
            self._owns_wf_root = True
        return self._work_folder_root

    def start(self) -> "EphemeralRuntime":
        if self._started:
            return self
        # Touch the work-folder root so it exists even if no write tool
        # is invoked; this also materializes the temp dir when one was
        # not supplied.
        _ = self.work_folder_root

        bus_url, bus_token, bus_cleanup = self._bus_spawner()
        self._bus_url = bus_url
        self._bus_gateway_token = bus_token
        self._cleanups.append(bus_cleanup)

        self._started = True
        if not self._atexit_registered:
            atexit.register(self.close)
            self._atexit_registered = True
        return self

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for cleanup in reversed(self._cleanups):
            try:
                cleanup()
            except Exception:
                # Best-effort cleanup: never mask the original error.
                pass
        self._cleanups.clear()
        if self._owns_wf_root and self._work_folder_root:
            shutil.rmtree(self._work_folder_root, ignore_errors=True)

    def __enter__(self) -> "EphemeralRuntime":
        return self.start()

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()


def default_bus_spawner() -> "tuple[str, str, Callable[[], None]]":
    """Spawn ``agent-bus-server --ephemeral`` and return (url, token, cleanup).

    agent-bus prints two lines to stdout on ephemeral boot:

        AGENT_BUS_EPHEMERAL_PORT=<port>
        AGENT_BUS_EPHEMERAL_TOKEN_FILE=<path>

    The token file holds ``BUS_GATEWAY_TOKEN=<token>``. We parse both,
    build the gateway URL, and return a cleanup that terminates the
    subprocess (which removes its own temp runtime root on exit).
    """
    proc = subprocess.Popen(
        [sys.executable, "-m", "agent_bus.http_server", "--ephemeral"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    port: Optional[int] = None
    token_file: Optional[str] = None
    deadline = time.time() + 30
    lines: list[str] = []
    while time.time() < deadline:
        line = proc.stdout.readline() if proc.stdout else ""
        if not line:
            if proc.poll() is not None:
                stderr = ""
                if proc.stderr:
                    stderr = proc.stderr.read()
                raise RuntimeError(
                    f"agent-bus ephemeral subprocess exited early: {stderr}"
                )
            time.sleep(0.05)
            continue
        line = line.strip()
        lines.append(line)
        if line.startswith("AGENT_BUS_EPHEMERAL_PORT="):
            try:
                port = int(line.split("=", 1)[1])
            except ValueError:
                pass
        elif line.startswith("AGENT_BUS_EPHEMERAL_TOKEN_FILE="):
            token_file = line.split("=", 1)[1]
        if port is not None and token_file is not None:
            break

    if port is None or token_file is None:
        proc.terminate()
        raise RuntimeError(
            f"agent-bus ephemeral subprocess did not report port/token: {lines}"
        )

    gateway_token = ""
    if os.path.exists(token_file):
        with open(token_file, "r", encoding="utf-8") as f:
            for raw in f:
                if raw.startswith("BUS_GATEWAY_TOKEN="):
                    gateway_token = raw.split("=", 1)[1].strip()
                    break

    url = f"http://127.0.0.1:{port}"

    def _cleanup() -> None:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    return url, gateway_token, _cleanup


class TempDirWorkFolderClient:
    """Work-folder client backed by a temp directory.

    Used in ephemeral mode so work-folder writes never reach the
    production katana-work-folder MCP. Implements the async ``call``
    interface the facets expect, operating on a local temp dir. The
    implementation is intentionally minimal but functional: file writes
    land on disk under ``<root>/<folder_id>/<filename>`` so callers can
    verify that writes are isolated to the temp dir.
    """

    def __init__(self, root: str) -> None:
        self._root = root
        os.makedirs(self._root, exist_ok=True)

    @property
    def root(self) -> str:
        return self._root

    async def call(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        handler = _WF_TOOLS.get(tool_name)
        if handler is None:
            return {"tool": tool_name, "arguments": arguments, "ok": True}
        return handler(self, arguments)


def _folder_dir(client: TempDirWorkFolderClient, folder_id: str) -> str:
    path = os.path.join(client.root, folder_id)
    os.makedirs(path, exist_ok=True)
    return path


def _safe_path(client: TempDirWorkFolderClient, folder_id: str, filename: str) -> str:
    folder = _folder_dir(client, folder_id)
    base = os.path.realpath(folder)
    target = os.path.realpath(os.path.join(folder, filename))
    if not target.startswith(base + os.sep) and target != base:
        raise ValueError(f"filename escapes folder root: {filename}")
    return target


def _wf_create(client: TempDirWorkFolderClient, args: dict[str, Any]) -> dict[str, Any]:
    topic = args.get("topic") or "ephemeral"
    folder_id = f"wf-{topic}"
    _folder_dir(client, folder_id)
    return {"folder_id": folder_id, "topic": topic, "created": True}


def _wf_list(client: TempDirWorkFolderClient, args: dict[str, Any]) -> dict[str, Any]:
    limit = args.get("limit", 10)
    entries = []
    if os.path.isdir(client.root):
        for name in sorted(os.listdir(client.root))[:limit]:
            entries.append({"folder_id": name})
    return {"folders": entries}


def _wf_save(client: TempDirWorkFolderClient, args: dict[str, Any]) -> dict[str, Any]:
    folder_id = args.get("folder_id", "")
    summary = args.get("summary", "checkpoint")
    path = os.path.join(_folder_dir(client, folder_id), "checkpoint.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary}, f)
    return {"folder_id": folder_id, "saved": True}


def _wf_resume(client: TempDirWorkFolderClient, args: dict[str, Any]) -> dict[str, Any]:
    return {"folder_id": args.get("folder_id", ""), "resumed": True}


def _wf_search(client: TempDirWorkFolderClient, args: dict[str, Any]) -> dict[str, Any]:
    return {"results": []}


def _wf_evidence_put(
    client: TempDirWorkFolderClient, args: dict[str, Any]
) -> dict[str, Any]:
    folder_id = args.get("folder_id", "")
    filename = args.get("filename", "evidence.txt")
    content = args.get("content", "")
    ev_dir = os.path.join(_folder_dir(client, folder_id), "evidence")
    os.makedirs(ev_dir, exist_ok=True)
    with open(os.path.join(ev_dir, filename), "w", encoding="utf-8") as f:
        f.write(content)
    return {"folder_id": folder_id, "filename": filename, "written": True}


def _wf_evidence_migrate(
    client: TempDirWorkFolderClient, args: dict[str, Any]
) -> dict[str, Any]:
    return {"folder_id": args.get("folder_id", ""), "migrated": True}


def _wf_append_progress(
    client: TempDirWorkFolderClient, args: dict[str, Any]
) -> dict[str, Any]:
    folder_id = args.get("folder_id", "")
    entry = args.get("entry", "")
    path = os.path.join(_folder_dir(client, folder_id), "progress.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"entry": entry}) + "\n")
    return {"folder_id": folder_id, "appended": True}


def _wf_reconcile(
    client: TempDirWorkFolderClient, args: dict[str, Any]
) -> dict[str, Any]:
    return {"reconciled": True}


def _wf_reindex(
    client: TempDirWorkFolderClient, args: dict[str, Any]
) -> dict[str, Any]:
    return {"reindexed": True}


def _fs_list(client: TempDirWorkFolderClient, args: dict[str, Any]) -> dict[str, Any]:
    folder_id = args.get("folder_id", "")
    dirname = args.get("dirname", "")
    path = os.path.join(_folder_dir(client, folder_id), dirname)
    if not os.path.isdir(path):
        return {"entries": []}
    return {
        "entries": [
            {"name": n, "type": "dir" if os.path.isdir(os.path.join(path, n)) else "file"}
            for n in sorted(os.listdir(path))
        ]
    }


def _fs_read(client: TempDirWorkFolderClient, args: dict[str, Any]) -> dict[str, Any]:
    folder_id = args.get("folder_id", "")
    filename = args.get("filename", "")
    path = _safe_path(client, folder_id, filename)
    if not os.path.isfile(path):
        return {"error": "NOT_FOUND"}
    with open(path, "r", encoding="utf-8") as f:
        return {"content": f.read()}


def _fs_read_bytes(
    client: TempDirWorkFolderClient, args: dict[str, Any]
) -> dict[str, Any]:
    folder_id = args.get("folder_id", "")
    filename = args.get("filename", "")
    path = _safe_path(client, folder_id, filename)
    if not os.path.isfile(path):
        return {"error": "NOT_FOUND"}
    with open(path, "rb") as f:
        return {"bytes": f.read().hex()}


def _fs_stat(client: TempDirWorkFolderClient, args: dict[str, Any]) -> dict[str, Any]:
    folder_id = args.get("folder_id", "")
    filename = args.get("filename", "")
    path = _safe_path(client, folder_id, filename)
    if not os.path.exists(path):
        return {"error": "NOT_FOUND"}
    st = os.stat(path)
    return {"size": st.st_size, "is_dir": os.path.isdir(path)}


def _fs_resolve(client: TempDirWorkFolderClient, args: dict[str, Any]) -> dict[str, Any]:
    return {"folder_id": args.get("folder_id", ""), "filename": args.get("filename", "")}


def _fs_create(client: TempDirWorkFolderClient, args: dict[str, Any]) -> dict[str, Any]:
    folder_id = args.get("folder_id", "")
    filename = args.get("filename", "")
    content = args.get("content", "")
    path = _safe_path(client, folder_id, filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"folder_id": folder_id, "filename": filename, "created": True}


def _fs_write(client: TempDirWorkFolderClient, args: dict[str, Any]) -> dict[str, Any]:
    folder_id = args.get("folder_id", "")
    filename = args.get("filename", "")
    content = args.get("content", "")
    path = _safe_path(client, folder_id, filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"folder_id": folder_id, "filename": filename, "written": True}


def _fs_edit(client: TempDirWorkFolderClient, args: dict[str, Any]) -> dict[str, Any]:
    folder_id = args.get("folder_id", "")
    filename = args.get("filename", "")
    old_string = args.get("old_string", "")
    new_string = args.get("new_string", "")
    replace_all = bool(args.get("replace_all", False))
    path = _safe_path(client, folder_id, filename)
    if not os.path.isfile(path):
        return {"error": "NOT_FOUND"}
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if replace_all:
        content = content.replace(old_string, new_string)
    else:
        content = content.replace(old_string, new_string, 1)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"folder_id": folder_id, "filename": filename, "edited": True}


def _fs_delete(client: TempDirWorkFolderClient, args: dict[str, Any]) -> dict[str, Any]:
    folder_id = args.get("folder_id", "")
    filename = args.get("filename", "")
    path = _safe_path(client, folder_id, filename)
    if os.path.exists(path):
        os.remove(path)
    return {"folder_id": folder_id, "filename": filename, "deleted": True}


def _fs_copy(client: TempDirWorkFolderClient, args: dict[str, Any]) -> dict[str, Any]:
    src_folder = args.get("source_folder_id", "")
    src_file = args.get("source_filename", "")
    dst_folder = args.get("dest_folder_id", "")
    dst_file = args.get("dest_filename", "")
    src = _safe_path(client, src_folder, src_file)
    dst = _safe_path(client, dst_folder, dst_file)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(src):
        shutil.copyfile(src, dst)
    return {"copied": True}


def _fs_rename(client: TempDirWorkFolderClient, args: dict[str, Any]) -> dict[str, Any]:
    src_folder = args.get("source_folder_id", "")
    src_file = args.get("source_filename", "")
    dst_folder = args.get("dest_folder_id", "")
    dst_file = args.get("dest_filename", "")
    src = _safe_path(client, src_folder, src_file)
    dst = _safe_path(client, dst_folder, dst_file)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(src):
        os.replace(src, dst)
    return {"renamed": True}


def _fs_batch(client: TempDirWorkFolderClient, args: dict[str, Any]) -> dict[str, Any]:
    folder_id = args.get("folder_id", "")
    operations = args.get("operations", [])
    for op in operations:
        op_name = op.get("op", "")
        if op_name in ("create", "write"):
            _fs_write(client, {"folder_id": folder_id, **op})
        elif op_name == "delete":
            _fs_delete(client, {"folder_id": folder_id, **op})
    return {"folder_id": folder_id, "batch_size": len(operations)}


def _fs_capabilities(
    client: TempDirWorkFolderClient, args: dict[str, Any]
) -> dict[str, Any]:
    return {"capabilities": ["fs_create", "fs_write", "fs_read", "fs_list", "fs_delete"]}


_WF_TOOLS: dict[str, Callable[[TempDirWorkFolderClient, dict[str, Any]], Any]] = {
    "wf_create": _wf_create,
    "wf_list": _wf_list,
    "wf_resume": _wf_resume,
    "wf_save": _wf_save,
    "wf_search": _wf_search,
    "wf_evidence_put": _wf_evidence_put,
    "wf_evidence_migrate": _wf_evidence_migrate,
    "wf_append_progress": _wf_append_progress,
    "wf_reconcile": _wf_reconcile,
    "wf_reindex": _wf_reindex,
    "fs_list": _fs_list,
    "fs_read": _fs_read,
    "fs_read_bytes": _fs_read_bytes,
    "fs_stat": _fs_stat,
    "fs_resolve": _fs_resolve,
    "fs_create": _fs_create,
    "fs_write": _fs_write,
    "fs_edit": _fs_edit,
    "fs_delete": _fs_delete,
    "fs_copy": _fs_copy,
    "fs_rename": _fs_rename,
    "fs_batch": _fs_batch,
    "fs_capabilities": _fs_capabilities,
}
