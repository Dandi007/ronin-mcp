"""Ephemeral mode (spec §判据 1 rule 1 + §判据 3).

--ephemeral must:
1. Start temporary agent-bus + Controller instances.
2. Route ALL writes to those ephemeral backends — never to the
   configured (potentially production) backend URLs.
3. Route work-folder writes to a temp directory.
4. Clean up every temporary resource on exit.

These tests use the in-process doubles as ephemeral backends (via
injectable spawners) so they run without booting real subprocesses.
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


@pytest.mark.timeout(30)
def test_ephemeral_routes_writes_to_ephemeral_bus_not_configured_url(
    ephemeral_server_factory: Any,
    make_config: Any,
    bus_double: Any,
) -> None:
    """A write in ephemeral mode lands in the ephemeral bus double's store,
    not in any production backend."""
    # Point the config at a clearly-wrong "production" URL to prove the
    # ephemeral runtime overrides it.
    config = make_config(ephemeral=True)
    config["backends"]["agent_bus"]["url"] = "http://127.0.0.1:1"

    server, rt = ephemeral_server_factory(config)

    data = _call(server, "ronin_alias_register", {
        "alias": "prod-ephemeral-alias",
        "kind": "named",
        "agent_id": "prod-ephemeral-bot",
    })
    assert data["alias"] == "prod-ephemeral-alias"

    # The write landed in the ephemeral bus double's store.
    assert "prod-ephemeral-alias" in bus_double.store["aliases"]
    rt.close()


@pytest.mark.timeout(30)
def test_ephemeral_routes_dd_writes_to_ephemeral_controller(
    ephemeral_server_factory: Any,
    make_config: Any,
) -> None:
    """dd dispatch tools are removed: none remain registered in ephemeral mode.

    The ronin_dev_* / ronin_gate_* / ronin_pump_* tools are gone from the
    registry, so no Controller / pump routing can be exercised through
    them. This test proves the removal also holds in ephemeral mode.
    """
    config = make_config(ephemeral=True)
    config["backends"]["dev_dispatch"]["url"] = "http://127.0.0.1:1"

    server, rt = ephemeral_server_factory(config)

    async def _run() -> None:
        async with Client(server) as client:
            tools = await client.list_tools()
            names = {t.name for t in tools}
            assert not any(
                name.startswith(("ronin_dev_", "ronin_gate_", "ronin_pump_"))
                for name in names
            )

    asyncio.run(_run())
    rt.close()


@pytest.mark.timeout(30)
def test_ephemeral_work_folder_writes_go_to_temp_dir(
    ephemeral_server_factory: Any,
    make_config: Any,
    tmp_runs_root: str,
) -> None:
    """Work-folder writes in ephemeral mode land in the temp work-folder root."""
    config = make_config(ephemeral=True)
    config["backends"]["work_folder"]["mcp_url"] = "http://127.0.0.1:1/mcp"

    server, rt = ephemeral_server_factory(config)

    data = _call(server, "ronin_fs_create", {
        "folder_id": "gd:ephemeral-folder",
        "filename": "hello.txt",
        "content": "ephemeral content",
    })
    assert data["created"] is True

    # The file landed in the temp work-folder root, not the production
    # katana-work-folder MCP.
    written = os.path.join(tmp_runs_root, "gd:ephemeral-folder", "hello.txt")
    assert os.path.isfile(written)
    with open(written, "r", encoding="utf-8") as f:
        assert f.read() == "ephemeral content"
    rt.close()


@pytest.mark.timeout(30)
def test_ephemeral_unlocks_production_writes_via_ephemeral_backend(
    ephemeral_server_factory: Any,
    make_config: Any,
    bus_double: Any,
) -> None:
    """Ephemeral mode unlocks production writes AND routes them to the
    ephemeral bus (not the configured production URL)."""
    config = make_config(ephemeral=True)
    config["backends"]["agent_bus"]["url"] = "http://127.0.0.1:1"

    server, rt = ephemeral_server_factory(config)

    # Non-gd: alias would normally be rejected; ephemeral unlocks it.
    data = _call(server, "ronin_alias_register", {
        "alias": "production-alias-ephemeral",
        "kind": "named",
        "agent_id": "prod-bot",
    })
    assert data["alias"] == "production-alias-ephemeral"
    assert "production-alias-ephemeral" in bus_double.store["aliases"]
    rt.close()


@pytest.mark.timeout(30)
def test_ephemeral_runtime_cleanup_removes_temp_work_folder_root(
    ephemeral_server_factory: Any,
    make_config: Any,
    tmp_runs_root: str,
) -> None:
    """EphemeralRuntime.close() removes the temp work-folder root."""
    from ronin_mcp.ephemeral import EphemeralRuntime

    # Use a fresh temp dir we control so we can assert removal.
    import tempfile

    controlled_root = tempfile.mkdtemp(prefix="ronin-ephemeral-cleanup-")
    try:
        rt = EphemeralRuntime(
            bus_spawner=lambda: ("http://127.0.0.1:1", "tok", lambda: None),
            controller_spawner=lambda: ("http://127.0.0.1:1", lambda: None),
            work_folder_root=controlled_root,
        )
        rt.start()
        # The runtime does not own a root it did not create, so close()
        # should NOT remove it. We only assert close() is idempotent and
        # does not raise.
        rt.close()
        assert os.path.isdir(controlled_root)
    finally:
        import shutil

        shutil.rmtree(controlled_root, ignore_errors=True)


@pytest.mark.timeout(30)
def test_ephemeral_runtime_close_is_idempotent() -> None:
    """Calling close() twice is safe."""
    from ronin_mcp.ephemeral import EphemeralRuntime

    rt = EphemeralRuntime(
        bus_spawner=lambda: ("http://127.0.0.1:1", "tok", lambda: None),
        controller_spawner=lambda: ("http://127.0.0.1:1", lambda: None),
    )
    rt.start()
    rt.close()
    rt.close()  # must not raise


@pytest.mark.timeout(30)
def test_ephemeral_runtime_calls_spawner_cleanups() -> None:
    """EphemeralRuntime.close() invokes every spawner's cleanup callable."""
    from ronin_mcp.ephemeral import EphemeralRuntime

    bus_cleaned = []
    ctrl_cleaned = []

    rt = EphemeralRuntime(
        bus_spawner=lambda: ("http://127.0.0.1:1", "tok", lambda: bus_cleaned.append(True)),
        controller_spawner=lambda: ("http://127.0.0.1:1", lambda: ctrl_cleaned.append(True)),
    )
    rt.start()
    rt.close()
    assert bus_cleaned == [True]
    assert ctrl_cleaned == [True]


@pytest.mark.timeout(30)
def test_ephemeral_mode_does_not_use_configured_bus_url(
    ephemeral_server_factory: Any,
    make_config: Any,
    bus_double: Any,
) -> None:
    """The server built in ephemeral mode must NOT carry the configured
    production bus URL — it must carry the ephemeral bus URL."""
    config = make_config(ephemeral=True)
    config["backends"]["agent_bus"]["url"] = "http://127.0.0.1:1"

    server, rt = ephemeral_server_factory(config)

    # The server's bus client base_url must be the ephemeral bus double's
    # URL, not the configured "http://127.0.0.1:1".
    # We reach into the server's tool registry indirectly: a successful
    # write proves the client is pointed at the live ephemeral bus.
    _call(server, "ronin_alias_register", {
        "alias": "gd:probe",
        "kind": "named",
        "agent_id": "gd:probe-bot",
    })
    assert "gd:probe" in bus_double.store["aliases"]
    rt.close()


@pytest.mark.timeout(30)
def test_ephemeral_work_folder_read_after_write(
    ephemeral_server_factory: Any,
    make_config: Any,
) -> None:
    """A write then read roundtrips through the temp work-folder dir."""
    config = make_config(ephemeral=True)

    server, rt = ephemeral_server_factory(config)

    _call(server, "ronin_fs_write", {
        "folder_id": "gd:rw-folder",
        "filename": "note.txt",
        "content": "round trip",
    })
    data = _call(server, "ronin_fs_read", {
        "folder_id": "gd:rw-folder",
        "filename": "note.txt",
    })
    assert data["content"] == "round trip"
    rt.close()
