"""Tool disposition SSoT for ronin-mcp.

Every ``ronin_*`` tool exposed by the single MCP server has exactly one
disposition, recorded here as the single source of truth (SSoT):

    available   the tool is active and its behaviour is unchanged.
    fixed       the tool is active and a defect in its call path has been
                repaired (see the ``reason`` field).

The retired dd-dispatch / gate / pump surfaces (``ronin_dev_*`` /
``ronin_gate_*`` / ``ronin_pump_*``) were removed outright in the
wf-525fd4 M3 follow-up decision (remove, do not redirect): their tool
registrations no longer exist, so they have no disposition entry here.
"""

from __future__ import annotations

AVAILABLE = "available"
FIXED = "fixed"

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
}


def disposition_of(tool_name: str) -> str:
    """Return the disposition string for a tool (must be a known tool)."""
    return DISPOSITIONS[tool_name]["disposition"]