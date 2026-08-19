"""MCP tool registry: exact tool set and parameter mapping."""

from __future__ import annotations

import asyncio

import pytest

from tests.conftest import _make_server


def _tools(mcp) -> set[str]:
    return {t.name for t in asyncio.run(mcp.list_tools())}


class TestToolRegistry:
    def test_exact_tool_names(self) -> None:
        mcp = _make_server()
        names = _tools(mcp)
        expected = {
            # alias
            "ronin_alias_list", "ronin_alias_resolve", "ronin_alias_register",
            "ronin_alias_rebind", "ronin_agent_list", "ronin_agent_whoami",
            "ronin_agent_register",
            # chatgroup
            "ronin_chatgroup_create", "ronin_chatgroup_list", "ronin_chatgroup_get",
            "ronin_chatgroup_add_member", "ronin_chatgroup_remove_member",
            "ronin_chatgroup_send",
            # messaging
            "ronin_msg_send", "ronin_msg_broadcast", "ronin_inbox_consume",
            "ronin_inbox_ack", "ronin_inbox_nack", "ronin_inbox_renew",
            "ronin_msg_read", "ronin_msg_events",
            # development
            "ronin_dev_list", "ronin_dev_get", "ronin_dev_events", "ronin_dev_evidence",
            "ronin_dev_create", "ronin_dev_start", "ronin_dev_steer",
            "ronin_dev_reconfigure", "ronin_dev_control", "ronin_dev_relock",
            # work folder
            "ronin_wf_list", "ronin_wf_create", "ronin_wf_resume", "ronin_wf_save",
            "ronin_wf_search", "ronin_wf_evidence_put", "ronin_wf_evidence_migrate",
            "ronin_wf_append_progress", "ronin_wf_reconcile", "ronin_wf_reindex",
            "ronin_fs_list", "ronin_fs_read", "ronin_fs_read_bytes", "ronin_fs_stat",
            "ronin_fs_resolve", "ronin_fs_create", "ronin_fs_write", "ronin_fs_edit",
            "ronin_fs_delete", "ronin_fs_copy", "ronin_fs_rename", "ronin_fs_batch",
            "ronin_fs_capabilities",
            # pump
            "ronin_pump_list", "ronin_pump_get", "ronin_pump_rounds",
            # gate
            "ronin_gate_approve", "ronin_gate_reject",
        }
        assert names == expected, f"missing={expected - names} extra={names - expected}"

    def test_tool_count(self) -> None:
        mcp = _make_server()
        tools = asyncio.run(mcp.list_tools())
        assert len(tools) == 59

    @pytest.mark.parametrize("name,required", [
        ("ronin_dev_create", {"name", "goal", "idempotency_key", "reason", "initial_handoff"}),
        ("ronin_dev_start", {"development_id", "idempotency_key", "expected_revision"}),
        ("ronin_gate_approve", {"development_id", "gate_id", "idempotency_key",
                                "expected_revision", "operator_identity"}),
        ("ronin_alias_register", {"alias", "kind", "agent_id"}),
    ])
    def test_required_parameters(self, name: str, required: set[str]) -> None:
        mcp = _make_server()
        tools = {t.name: t for t in asyncio.run(mcp.list_tools())}
        tool = tools[name]
        assert required.issubset(set(tool.parameters["required"])), tool.parameters["required"]

    def test_no_token_parameters(self) -> None:
        mcp = _make_server()
        for t in asyncio.run(mcp.list_tools()):
            props = t.parameters["properties"]
            assert "token" not in props, f"{t.name} exposes a token parameter"
            assert "gateway_token" not in props, f"{t.name} exposes gateway_token"
            assert "bus_admin_token" not in props, f"{t.name} exposes bus_admin_token"
