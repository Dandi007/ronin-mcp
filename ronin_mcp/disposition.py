"""Tool disposition SSoT for ronin-mcp.

Every ``ronin_*`` tool exposed by the single MCP server has exactly one
disposition, recorded here as the single source of truth (SSoT):

    available   the tool is active and its behaviour is unchanged.
    fixed       the tool is active and a defect in its call path has been
                repaired (see the ``reason`` field).
    retired     the tool remains registered / visible in ``tools/list``
                but invocations are refused with an explicit, structured
                ``RETIRED`` rejection instead of surfacing as an
                ``Unknown tool`` or a backend fault.

The three categories are exhaustive: no tool may sit in a fourth state
where it appears in ``tools/list`` yet failure looks like an operational
fault (e.g. ``Connection refused`` / ``BACKEND_UNAVAILABLE``).
"""

from __future__ import annotations

from typing import Any

AVAILABLE = "available"
FIXED = "fixed"
RETIRED = "retired"

DISPOSITIONS: dict[str, dict[str, str]] = {
    # --- friend (alias) + agent registry -> agent-bus (available) ---
    "ronin_alias_list": {
        "disposition": AVAILABLE,
        "reason": "friend alias listing over agent-bus remains active.",
    },
    "ronin_alias_resolve": {
        "disposition": AVAILABLE,
        "reason": "alias resolution over agent-bus remains active.",
    },
    "ronin_alias_register": {
        "disposition": AVAILABLE,
        "reason": "alias registration over agent-bus remains active.",
    },
    "ronin_alias_rebind": {
        "disposition": AVAILABLE,
        "reason": "CAS alias rebind over agent-bus remains active.",
    },
    "ronin_agent_list": {
        "disposition": AVAILABLE,
        "reason": "agent listing over agent-bus remains active.",
    },
    "ronin_agent_whoami": {
        "disposition": AVAILABLE,
        "reason": "current-identity read over agent-bus remains active.",
    },
    "ronin_agent_register": {
        "disposition": AVAILABLE,
        "reason": "agent registration over agent-bus remains active.",
    },
    # --- chatgroup -> agent-bus (available) ---
    "ronin_chatgroup_create": {
        "disposition": AVAILABLE,
        "reason": "chatgroup creation over agent-bus remains active.",
    },
    "ronin_chatgroup_list": {
        "disposition": AVAILABLE,
        "reason": "chatgroup listing over agent-bus remains active.",
    },
    "ronin_chatgroup_get": {
        "disposition": AVAILABLE,
        "reason": "chatgroup detail read over agent-bus remains active.",
    },
    "ronin_chatgroup_add_member": {
        "disposition": AVAILABLE,
        "reason": "chatgroup member add over agent-bus remains active.",
    },
    "ronin_chatgroup_remove_member": {
        "disposition": AVAILABLE,
        "reason": "chatgroup member remove over agent-bus remains active.",
    },
    "ronin_chatgroup_send": {
        "disposition": AVAILABLE,
        "reason": "chatgroup broadcast over agent-bus remains active.",
    },
    # --- messaging / inbox -> agent-bus (available) ---
    "ronin_msg_send": {
        "disposition": AVAILABLE,
        "reason": "single-send messaging over agent-bus remains active.",
    },
    "ronin_msg_broadcast": {
        "disposition": AVAILABLE,
        "reason": "principal broadcast over agent-bus remains active.",
    },
    "ronin_inbox_consume": {
        "disposition": AVAILABLE,
        "reason": "inbox consume over agent-bus remains active.",
    },
    "ronin_inbox_ack": {
        "disposition": AVAILABLE,
        "reason": "delivery ack over agent-bus remains active.",
    },
    "ronin_inbox_nack": {
        "disposition": AVAILABLE,
        "reason": "delivery nack over agent-bus remains active.",
    },
    "ronin_inbox_renew": {
        "disposition": AVAILABLE,
        "reason": "lease renew over agent-bus remains active.",
    },
    "ronin_msg_read": {
        "disposition": AVAILABLE,
        "reason": "channel history read over agent-bus remains active.",
    },
    "ronin_msg_events": {
        "disposition": AVAILABLE,
        "reason": "bus event stream read over agent-bus remains active.",
    },
    # --- work folder / file ops -> katana-work-folder MCP (fixed) ---
    "ronin_wf_list": {
        "disposition": FIXED,
        "reason": "repaired asyncio.run()-in-running-event-loop to direct await.",
    },
    "ronin_wf_create": {
        "disposition": FIXED,
        "reason": "repaired asyncio.run()-in-running-event-loop to direct await.",
    },
    "ronin_wf_resume": {
        "disposition": FIXED,
        "reason": "repaired asyncio.run()-in-running-event-loop to direct await.",
    },
    "ronin_wf_save": {
        "disposition": FIXED,
        "reason": "repaired asyncio.run()-in-running-event-loop to direct await.",
    },
    "ronin_wf_search": {
        "disposition": FIXED,
        "reason": "repaired asyncio.run()-in-running-event-loop to direct await.",
    },
    "ronin_wf_evidence_put": {
        "disposition": FIXED,
        "reason": "repaired asyncio.run()-in-running-event-loop to direct await.",
    },
    "ronin_wf_evidence_migrate": {
        "disposition": FIXED,
        "reason": "repaired asyncio.run()-in-running-event-loop to direct await.",
    },
    "ronin_wf_append_progress": {
        "disposition": FIXED,
        "reason": "repaired asyncio.run()-in-running-event-loop to direct await.",
    },
    "ronin_wf_reconcile": {
        "disposition": FIXED,
        "reason": "repaired asyncio.run()-in-running-event-loop to direct await.",
    },
    "ronin_wf_reindex": {
        "disposition": FIXED,
        "reason": "repaired asyncio.run()-in-running-event-loop to direct await.",
    },
    "ronin_fs_list": {
        "disposition": FIXED,
        "reason": "repaired asyncio.run()-in-running-event-loop to direct await.",
    },
    "ronin_fs_read": {
        "disposition": FIXED,
        "reason": "repaired asyncio.run()-in-running-event-loop to direct await.",
    },
    "ronin_fs_read_bytes": {
        "disposition": FIXED,
        "reason": "repaired asyncio.run()-in-running-event-loop to direct await.",
    },
    "ronin_fs_stat": {
        "disposition": FIXED,
        "reason": "repaired asyncio.run()-in-running-event-loop to direct await.",
    },
    "ronin_fs_resolve": {
        "disposition": FIXED,
        "reason": "repaired asyncio.run()-in-running-event-loop to direct await.",
    },
    "ronin_fs_create": {
        "disposition": FIXED,
        "reason": "repaired asyncio.run()-in-running-event-loop to direct await.",
    },
    "ronin_fs_write": {
        "disposition": FIXED,
        "reason": "repaired asyncio.run()-in-running-event-loop to direct await.",
    },
    "ronin_fs_edit": {
        "disposition": FIXED,
        "reason": "repaired asyncio.run()-in-running-event-loop to direct await.",
    },
    "ronin_fs_delete": {
        "disposition": FIXED,
        "reason": "repaired asyncio.run()-in-running-event-loop to direct await.",
    },
    "ronin_fs_copy": {
        "disposition": FIXED,
        "reason": "repaired asyncio.run()-in-running-event-loop to direct await.",
    },
    "ronin_fs_rename": {
        "disposition": FIXED,
        "reason": "repaired asyncio.run()-in-running-event-loop to direct await.",
    },
    "ronin_fs_batch": {
        "disposition": FIXED,
        "reason": "repaired asyncio.run()-in-running-event-loop to direct await.",
    },
    "ronin_fs_capabilities": {
        "disposition": FIXED,
        "reason": "repaired asyncio.run()-in-running-event-loop to direct await.",
    },
    # --- dd dispatch lifecycle -> retired ---
    "ronin_dev_list": {
        "disposition": RETIRED,
        "reason": "dd dispatch listing is no longer ronin-mcp's surface "
        "(lifecycle owner: wf-3ffd90).",
    },
    "ronin_dev_get": {
        "disposition": RETIRED,
        "reason": "dd dispatch retrieval is no longer ronin-mcp's surface "
        "(lifecycle owner: wf-3ffd90).",
    },
    "ronin_dev_events": {
        "disposition": RETIRED,
        "reason": "dd dispatch event polling is no longer ronin-mcp's surface "
        "(lifecycle owner: wf-3ffd90).",
    },
    "ronin_dev_evidence": {
        "disposition": RETIRED,
        "reason": "dd dispatch evidence export is no longer ronin-mcp's surface "
        "(lifecycle owner: wf-3ffd90).",
    },
    "ronin_dev_create": {
        "disposition": RETIRED,
        "reason": "dd dispatch creation is no longer ronin-mcp's surface "
        "(lifecycle owner: wf-3ffd90).",
    },
    "ronin_dev_start": {
        "disposition": RETIRED,
        "reason": "dd dispatch start is no longer ronin-mcp's surface "
        "(lifecycle owner: wf-3ffd90).",
    },
    "ronin_dev_steer": {
        "disposition": RETIRED,
        "reason": "dd dispatch steering is no longer ronin-mcp's surface "
        "(lifecycle owner: wf-3ffd90).",
    },
    "ronin_dev_reconfigure": {
        "disposition": RETIRED,
        "reason": "dd dispatch reconfiguration is no longer ronin-mcp's surface "
        "(lifecycle owner: wf-3ffd90).",
    },
    "ronin_dev_control": {
        "disposition": RETIRED,
        "reason": "dd dispatch pause/resume/cancel is no longer ronin-mcp's surface "
        "(lifecycle owner: wf-3ffd90).",
    },
    "ronin_dev_relock": {
        "disposition": RETIRED,
        "reason": "dd dispatch plugin relock is no longer ronin-mcp's surface "
        "(lifecycle owner: wf-3ffd90).",
    },
    # --- gate approval -> retired ---
    "ronin_gate_approve": {
        "disposition": RETIRED,
        "reason": "gate approval is no longer ronin-mcp's surface "
        "(lifecycle owner: wf-3ffd90).",
    },
    "ronin_gate_reject": {
        "disposition": RETIRED,
        "reason": "gate rejection is no longer ronin-mcp's surface "
        "(lifecycle owner: wf-3ffd90).",
    },
    # --- pump state -> retired ---
    "ronin_pump_list": {
        "disposition": RETIRED,
        "reason": "pump run listing is no longer ronin-mcp's surface "
        "(lifecycle owner: wf-3ffd90).",
    },
    "ronin_pump_get": {
        "disposition": RETIRED,
        "reason": "pump run retrieval is no longer ronin-mcp's surface "
        "(lifecycle owner: wf-3ffd90).",
    },
    "ronin_pump_rounds": {
        "disposition": RETIRED,
        "reason": "pump round event reads are no longer ronin-mcp's surface "
        "(lifecycle owner: wf-3ffd90).",
    },
}

RETIRED_CODE = "RETIRED"


def disposition_of(tool_name: str) -> str:
    """Return the disposition string for a tool (must be a known tool)."""
    return DISPOSITIONS[tool_name]["disposition"]


def is_retired(tool_name: str) -> bool:
    """True when the tool is retired and must refuse with RETIRED."""
    return DISPOSITIONS[tool_name]["disposition"] == RETIRED


class ToolRetiredError(Exception):
    """Raised when a retired tool is invoked.

    Carries the canonical structured ``RETIRED`` envelope so the server
    layer can surface it to the caller as a ToolError whose message is
    parseable JSON (mirroring the backend-error convention):

        {"code": "RETIRED", "message": "...", "details": {"retryable": False}}
    """

    def __init__(self, tool_name: str) -> None:
        entry = DISPOSITIONS[tool_name]
        self.tool_name = tool_name
        self.reason = entry["reason"]
        super().__init__(f"Tool '{tool_name}' is retired: {self.reason}")

    @property
    def envelope(self) -> dict[str, Any]:
        return {
            "code": RETIRED_CODE,
            "message": f"Tool '{self.tool_name}' is retired: {self.reason}",
            "details": {"retryable": False},
        }


def retire(tool_name: str) -> Any:
    """Refuse an invocation on a retired tool (never returns)."""
    raise ToolRetiredError(tool_name)