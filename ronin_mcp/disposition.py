"""M3 disposition: authoritative per-tool judgement for all 59 ronin-mcp tools.

This module is the single source of truth for the M3 verdict ("修，或退役").
Every ronin-mcp tool is classified exactly once as one of three dispositions:

``available``
    The upstream backend is alive; the tool stays on the calling surface and
    works. This is the agent-bus family (alias / agent / chatgroup / msg / inbox).

``fixed``
    The tool had an implementation defect not an obsolete backend; the defect
    has been repaired and the tool stays on the calling surface. This is the
    work-folder / file-system family (``ronin_wf_*`` / ``ronin_fs_*``) whose
    ``asyncio.run()``-in-a-running-event-loop bug has been fixed.

``retired``
    The upstream backend is dead; the tool is removed from the calling surface
    and must never be presented as usable. This is the dev-dispatch (``ronin_dev_*``),
    gate (``ronin_gate_*``) and pump-state (``ronin_pump_*``) families.

The negative DoD ("不允许恒亮 / 退役可回归") is enforced by
``assert_live_surface``: any retired tool name that reappears on the live
calling surface raises ``DispositionError``. Tests build the server, read the
real ``tools/list``, and assert the live surface matches ``live_tools()`` exactly,
so re-adding a retired call turns a test red.
"""

from __future__ import annotations

from collections.abc import Collection

DISPOSITION_AVAILABLE = "available"
DISPOSITION_FIXED = "fixed"
DISPOSITION_RETIRED = "retired"

# Reasons attached to each retired family (真机取证 2026-09-02, wf-525fd4 goal.md M3).
RETIRE_REASON_DEV_DISPATCH = (
    "upstream dev-dispatch controller retired (BACKEND_UNAVAILABLE: controller GET /v1/developments Connection refused)"
)
RETIRE_REASON_PUMP = "pump stack retired (No such file or directory: /data/ronin/runs)"

# Per-tool disposition. All 59 tools, none missing, no overlaps.
TOOL_DISPOSITION: dict[str, str] = {
    # --- agent-bus family: alias / agent (7) ---
    "ronin_alias_list": DISPOSITION_AVAILABLE,
    "ronin_alias_resolve": DISPOSITION_AVAILABLE,
    "ronin_alias_register": DISPOSITION_AVAILABLE,
    "ronin_alias_rebind": DISPOSITION_AVAILABLE,
    "ronin_agent_list": DISPOSITION_AVAILABLE,
    "ronin_agent_whoami": DISPOSITION_AVAILABLE,
    "ronin_agent_register": DISPOSITION_AVAILABLE,
    # --- agent-bus family: chatgroup (6) ---
    "ronin_chatgroup_create": DISPOSITION_AVAILABLE,
    "ronin_chatgroup_list": DISPOSITION_AVAILABLE,
    "ronin_chatgroup_get": DISPOSITION_AVAILABLE,
    "ronin_chatgroup_add_member": DISPOSITION_AVAILABLE,
    "ronin_chatgroup_remove_member": DISPOSITION_AVAILABLE,
    "ronin_chatgroup_send": DISPOSITION_AVAILABLE,
    # --- agent-bus family: messaging (msg / inbox) (8) ---
    "ronin_msg_send": DISPOSITION_AVAILABLE,
    "ronin_msg_broadcast": DISPOSITION_AVAILABLE,
    "ronin_inbox_consume": DISPOSITION_AVAILABLE,
    "ronin_inbox_ack": DISPOSITION_AVAILABLE,
    "ronin_inbox_nack": DISPOSITION_AVAILABLE,
    "ronin_inbox_renew": DISPOSITION_AVAILABLE,
    "ronin_msg_read": DISPOSITION_AVAILABLE,
    "ronin_msg_events": DISPOSITION_AVAILABLE,
    # --- work-folder / file-system family (23): asyncio.run defect fixed ---
    "ronin_wf_list": DISPOSITION_FIXED,
    "ronin_wf_create": DISPOSITION_FIXED,
    "ronin_wf_resume": DISPOSITION_FIXED,
    "ronin_wf_save": DISPOSITION_FIXED,
    "ronin_wf_search": DISPOSITION_FIXED,
    "ronin_wf_evidence_put": DISPOSITION_FIXED,
    "ronin_wf_evidence_migrate": DISPOSITION_FIXED,
    "ronin_wf_append_progress": DISPOSITION_FIXED,
    "ronin_wf_reconcile": DISPOSITION_FIXED,
    "ronin_wf_reindex": DISPOSITION_FIXED,
    "ronin_fs_list": DISPOSITION_FIXED,
    "ronin_fs_read": DISPOSITION_FIXED,
    "ronin_fs_read_bytes": DISPOSITION_FIXED,
    "ronin_fs_stat": DISPOSITION_FIXED,
    "ronin_fs_resolve": DISPOSITION_FIXED,
    "ronin_fs_create": DISPOSITION_FIXED,
    "ronin_fs_write": DISPOSITION_FIXED,
    "ronin_fs_edit": DISPOSITION_FIXED,
    "ronin_fs_delete": DISPOSITION_FIXED,
    "ronin_fs_copy": DISPOSITION_FIXED,
    "ronin_fs_rename": DISPOSITION_FIXED,
    "ronin_fs_batch": DISPOSITION_FIXED,
    "ronin_fs_capabilities": DISPOSITION_FIXED,
    # --- dev-dispatch family (10): retired ---
    "ronin_dev_list": DISPOSITION_RETIRED,
    "ronin_dev_get": DISPOSITION_RETIRED,
    "ronin_dev_events": DISPOSITION_RETIRED,
    "ronin_dev_evidence": DISPOSITION_RETIRED,
    "ronin_dev_create": DISPOSITION_RETIRED,
    "ronin_dev_start": DISPOSITION_RETIRED,
    "ronin_dev_steer": DISPOSITION_RETIRED,
    "ronin_dev_reconfigure": DISPOSITION_RETIRED,
    "ronin_dev_control": DISPOSITION_RETIRED,
    "ronin_dev_relock": DISPOSITION_RETIRED,
    # --- gate family (2): retired ---
    "ronin_gate_approve": DISPOSITION_RETIRED,
    "ronin_gate_reject": DISPOSITION_RETIRED,
    # --- pump state family (3): retired ---
    "ronin_pump_list": DISPOSITION_RETIRED,
    "ronin_pump_get": DISPOSITION_RETIRED,
    "ronin_pump_rounds": DISPOSITION_RETIRED,
}

# Per-tool reason for the retired tools; every retired tool has a reason.
RETIRED_TOOL_REASONS: dict[str, str] = {
    "ronin_dev_list": RETIRE_REASON_DEV_DISPATCH,
    "ronin_dev_get": RETIRE_REASON_DEV_DISPATCH,
    "ronin_dev_events": RETIRE_REASON_DEV_DISPATCH,
    "ronin_dev_evidence": RETIRE_REASON_DEV_DISPATCH,
    "ronin_dev_create": RETIRE_REASON_DEV_DISPATCH,
    "ronin_dev_start": RETIRE_REASON_DEV_DISPATCH,
    "ronin_dev_steer": RETIRE_REASON_DEV_DISPATCH,
    "ronin_dev_reconfigure": RETIRE_REASON_DEV_DISPATCH,
    "ronin_dev_control": RETIRE_REASON_DEV_DISPATCH,
    "ronin_dev_relock": RETIRE_REASON_DEV_DISPATCH,
    "ronin_gate_approve": RETIRE_REASON_DEV_DISPATCH,
    "ronin_gate_reject": RETIRE_REASON_DEV_DISPATCH,
    "ronin_pump_list": RETIRE_REASON_PUMP,
    "ronin_pump_get": RETIRE_REASON_PUMP,
    "ronin_pump_rounds": RETIRE_REASON_PUMP,
}

TOTAL_TOOL_COUNT = 59


class DispositionError(ValueError):
    """Raised when the live calling surface violates the disposition registry."""


def all_tools() -> frozenset[str]:
    """The full 59-tool catalog."""
    return frozenset(TOOL_DISPOSITION)


def _tools_with(disposition: str) -> frozenset[str]:
    return frozenset(name for name, disp in TOOL_DISPOSITION.items() if disp == disposition)


def available_tools() -> frozenset[str]:
    """Tools whose upstream backend is alive (agent-bus family)."""
    return _tools_with(DISPOSITION_AVAILABLE)


def fixed_tools() -> frozenset[str]:
    """Tools whose implementation defect was repaired (work-folder family)."""
    return _tools_with(DISPOSITION_FIXED)


def retired_tools() -> frozenset[str]:
    """Tools retired because their upstream backend is dead."""
    return _tools_with(DISPOSITION_RETIRED)


def live_tools() -> frozenset[str]:
    """The intended calling surface: available + fixed (retired excluded)."""
    return available_tools() | fixed_tools()


def assert_live_surface(live_names: Collection[str]) -> None:
    """Raise ``DispositionError`` if any retired tool reappears on the surface.

    This is the regressable guard behind the negative DoD: re-adding a retired
    call (e.g. re-registering ``ronin_pump_list`` as a working tool) makes this
    raise, and a test that feeds a contaminated surface turns red.
    """
    stray_retired = retired_tools() & frozenset(live_names)
    if stray_retired:
        raise DispositionError(
            "retired tools must not be on the live calling surface: " + ", ".join(sorted(stray_retired))
        )
