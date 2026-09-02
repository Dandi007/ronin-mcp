"""M3 disposition acceptance tests (goal.md M3 / DoD 3).

These tests pin the "修，或退役" verdict for all 59 ronin-mcp tools:

* positive (DoD 3): every tool is either available or fixed (and therefore on
  the live calling surface), or explicitly retired (and therefore absent from
  the live calling surface) — no third "looks usable but backend is dead" state.
* negative (不允许恒亮 / 退役可回归): a retired tool that is re-added to the
  calling surface is caught — the live surface must equal ``live_tools()``
  exactly, and ``assert_live_surface`` raises on any stray retired name.

The retired families (dev-dispatch / gate / pump) are exercised only as
*absences* here; re-registering them turns ``test_live_surface_matches_registry``
red. The work-folder / file-system family (fixed) is additionally exercised
through a real async backend double to prove the ``asyncio.run()`` defect is
gone.
"""

from __future__ import annotations

import asyncio
import copy
import json
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError

import ronin_mcp.disposition as disposition
from ronin_mcp.config import DEFAULT_CONFIG
from ronin_mcp.server import build_mcp_server

RETIRED_DEV_GATE = {
    "ronin_dev_list",
    "ronin_dev_get",
    "ronin_dev_events",
    "ronin_dev_evidence",
    "ronin_dev_create",
    "ronin_dev_start",
    "ronin_dev_steer",
    "ronin_dev_reconfigure",
    "ronin_dev_control",
    "ronin_dev_relock",
    "ronin_gate_approve",
    "ronin_gate_reject",
}

RETIRED_PUMP = {
    "ronin_pump_list",
    "ronin_pump_get",
    "ronin_pump_rounds",
}

FIXED_WF_FS = {
    "ronin_wf_list",
    "ronin_wf_create",
    "ronin_wf_resume",
    "ronin_wf_save",
    "ronin_wf_search",
    "ronin_wf_evidence_put",
    "ronin_wf_evidence_migrate",
    "ronin_wf_append_progress",
    "ronin_wf_reconcile",
    "ronin_wf_reindex",
    "ronin_fs_list",
    "ronin_fs_read",
    "ronin_fs_read_bytes",
    "ronin_fs_stat",
    "ronin_fs_resolve",
    "ronin_fs_create",
    "ronin_fs_write",
    "ronin_fs_edit",
    "ronin_fs_delete",
    "ronin_fs_copy",
    "ronin_fs_rename",
    "ronin_fs_batch",
    "ronin_fs_capabilities",
}


def _config(*, prod_write: bool = False, ephemeral: bool = False) -> dict[str, Any]:
    cfg = copy.deepcopy(DEFAULT_CONFIG)
    cfg["auth"]["prod_write_enabled"] = prod_write
    cfg["auth"]["ephemeral"] = ephemeral
    return cfg


def _build(*, prod_write: bool = False, ephemeral: bool = False) -> Any:
    return build_mcp_server(_config(prod_write=prod_write, ephemeral=ephemeral))


def _tool_names(server: Any) -> set[str]:
    async def _run() -> set[str]:
        async with Client(server) as client:
            tools = await client.list_tools()
            return {t.name for t in tools}

    return asyncio.run(_run())


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


def _error_envelope(exc: ToolError) -> dict[str, Any]:
    raw = str(exc)
    start = raw.find("{")
    end = raw.rfind("}")
    assert start != -1 and end > start, f"no JSON envelope in {raw!r}"
    return json.loads(raw[start : end + 1])


class _AsyncWorkFolderDouble:
    """Mirrors the real ``WorkFolderClient``: an async ``call`` entry plus the
    legacy buggy ``call_sync`` that used ``asyncio.run`` (which cannot run from
    inside FastMCP's event loop)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((tool_name, dict(arguments)))
        return {"tool": tool_name, "arguments": arguments, "ok": True}

    def call_sync(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        # The old defect: asyncio.run() cannot be called from a running loop.
        return asyncio.run(self.call(tool_name, arguments))


class _FailingWorkFolderDouble:
    """An async work-folder double whose backend is unreachable."""

    async def call(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        from ronin_mcp.backends.agent_bus import BackendError

        raise BackendError(
            f"work-folder MCP {tool_name} unavailable",
            code="BACKEND_UNAVAILABLE",
            retryable=True,
        )


def test_registry_covers_all_59_tools() -> None:
    """The registry is a complete, non-overlapping partition of all 59 tools."""
    assert disposition.TOTAL_TOOL_COUNT == 59
    assert len(disposition.all_tools()) == 59
    assert len(disposition.available_tools()) == 21
    assert len(disposition.fixed_tools()) == 23
    assert len(disposition.retired_tools()) == 15

    avail, fixed, retired = (
        disposition.available_tools(),
        disposition.fixed_tools(),
        disposition.retired_tools(),
    )
    assert avail.isdisjoint(fixed)
    assert avail.isdisjoint(retired)
    assert fixed.isdisjoint(retired)
    assert avail | fixed | retired == disposition.all_tools()


def test_every_retired_tool_has_a_reason() -> None:
    """Retirement is explicit: every retired tool carries a documented reason."""
    assert set(disposition.RETIRED_TOOL_REASONS) == disposition.retired_tools()
    for name in disposition.retired_tools():
        assert disposition.RETIRED_TOOL_REASONS[name]


def test_retired_tools_are_dev_gate_pump() -> None:
    """The retired set is exactly dev-dispatch + gate + pump-state."""
    assert disposition.retired_tools() == RETIRED_DEV_GATE | RETIRED_PUMP


def test_fixed_tools_are_work_folder_family() -> None:
    """The fixed set is exactly the wf/fs family (implementation defect, not dead)."""
    assert disposition.fixed_tools() == FIXED_WF_FS


def test_live_surface_matches_registry_exactly() -> None:
    """The built server registers exactly the intended live surface.

    This is the DoD-3 hinge: any retired tool that is re-registered appears as a
    stray name and fails the exact-set equality (negative DoD: retired-call
    regression turns red).
    """
    actual = _tool_names(_build())
    assert actual == disposition.live_tools()


def test_retired_tools_absent_from_live_surface() -> None:
    """No retired tool may stay exposed as usable (no up=1 while dead)."""
    actual = _tool_names(_build())
    for name in sorted(disposition.retired_tools()):
        assert name not in actual, f"retired tool {name} still exposed"


def test_assert_live_surface_accepts_clean_surface() -> None:
    """The regressable guard passes on a clean surface."""
    disposition.assert_live_surface(disposition.live_tools())


def test_assert_live_surface_rejects_retired_regression() -> None:
    """Re-adding a retired call makes the guard raise (negative DoD)."""
    contaminated = disposition.live_tools() | {"ronin_pump_list"}
    with pytest.raises(disposition.DispositionError):
        disposition.assert_live_surface(contaminated)


def test_wf_fs_tools_await_async_backend_without_asyncio_run() -> None:
    """wf/fs tools call the backend's async ``call`` entry directly.

    The double still carries the buggy ``call_sync``; if the facet fell back to
    it, ``asyncio.run()`` inside FastMCP's event loop would raise RuntimeError
    and this test would fail. Success proves the ``asyncio.run()`` defect is
    fixed.
    """
    double = _AsyncWorkFolderDouble()
    server = build_mcp_server(_config(), work_folder_client=double)

    assert _call(server, "ronin_wf_list", {"limit": 3})["tool"] == "wf_list"
    assert _call(server, "ronin_fs_list", {"folder_id": "gd:f", "dirname": ""})["tool"] == "fs_list"
    assert ("wf_list", {"limit": 3}) in double.calls
    assert ("fs_list", {"folder_id": "gd:f", "dirname": ""}) in double.calls


def test_wf_fs_backend_unavailable_surfaces_structured_envelope() -> None:
    """Async work-folder failures surface the canonical structured envelope."""
    server = build_mcp_server(_config(), work_folder_client=_FailingWorkFolderDouble())

    async def _run() -> None:
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc:
                await client.call_tool("ronin_wf_list", {})
            env = _error_envelope(exc.value)
            assert env["code"] == "BACKEND_UNAVAILABLE"
            assert env["details"]["retryable"] is True

    asyncio.run(_run())


def test_bus_tools_still_usable(mcp_server_factory: Any, make_config: Any) -> None:
    """Available tools (agent-bus family) remain genuinely usable."""
    server = mcp_server_factory(make_config())
    data = _call(server, "ronin_agent_whoami", {})
    assert "agent_id" in data
