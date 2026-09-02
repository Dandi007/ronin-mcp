"""Write-side guardrails (spec §判据 1).

The entrance must:
- allow gd:-prefixed writes without explicit authorization
- reject production writes (non-gd:) when RONIN_PROD_WRITE is unset
- allow production writes when RONIN_PROD_WRITE=1 / --prod-write
- unlock everything in ephemeral mode
- always require prod write for gate approvals (even gd:)
- always require prod write for broadcast (online humans)
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastmcp import Client
from fastmcp.exceptions import ToolError


def _extract_text(result: Any) -> str:
    if hasattr(result, "content") and result.content:
        return result.content[0].text
    if hasattr(result, "text"):
        return result.text
    return str(result)


@pytest.mark.timeout(30)
def test_gd_alias_register_allowed_without_prod_write(mcp_server_factory: Any, make_config: Any) -> None:
    """gd:-prefixed alias registration is allowed without prod write."""
    server = mcp_server_factory(make_config())

    async def _run() -> None:
        async with Client(server) as client:
            result = await client.call_tool(
                "ronin_alias_register",
                {"alias": "gd:test-alias", "kind": "named", "agent_id": "gd:test-bot"},
            )
            data = json.loads(_extract_text(result))
            assert data["alias"] == "gd:test-alias"
            assert data["current_agent_id"] == "gd:test-bot"

    import asyncio
    asyncio.run(_run())


@pytest.mark.timeout(30)
def test_prod_alias_register_rejected_without_prod_write(mcp_server_factory: Any, make_config: Any) -> None:
    """Production alias registration is rejected without prod write."""
    server = mcp_server_factory(make_config())

    async def _run() -> None:
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc_info:
                await client.call_tool(
                    "ronin_alias_register",
                    {"alias": "production-alias", "kind": "named", "agent_id": "prod-bot"},
                )
            message = str(exc_info.value)
            assert "PROD_WRITE_NOT_AUTHORIZED" in message

    import asyncio
    asyncio.run(_run())


@pytest.mark.timeout(30)
def test_prod_alias_register_allowed_with_prod_write(mcp_server_factory: Any, make_config: Any) -> None:
    """Production alias registration succeeds with prod write enabled."""
    server = mcp_server_factory(make_config(prod_write=True))

    async def _run() -> None:
        async with Client(server) as client:
            result = await client.call_tool(
                "ronin_alias_register",
                {"alias": "production-alias", "kind": "named", "agent_id": "prod-bot"},
            )
            data = json.loads(_extract_text(result))
            assert data["alias"] == "production-alias"

    import asyncio
    asyncio.run(_run())


@pytest.mark.timeout(30)
def test_ephemeral_unlocks_production_writes(mcp_server_factory: Any, make_config: Any) -> None:
    """Ephemeral mode unlocks production writes."""
    server = mcp_server_factory(make_config(ephemeral=True))

    async def _run() -> None:
        async with Client(server) as client:
            result = await client.call_tool(
                "ronin_alias_register",
                {"alias": "prod-ephemeral", "kind": "named", "agent_id": "prod-bot"},
            )
            data = json.loads(_extract_text(result))
            assert data["alias"] == "prod-ephemeral"

    import asyncio
    asyncio.run(_run())


@pytest.mark.timeout(30)
def test_broadcast_always_requires_prod_write(mcp_server_factory: Any, make_config: Any) -> None:
    """Broadcast to online humans always requires prod write (even gd: payload)."""
    server = mcp_server_factory(make_config())

    async def _run() -> None:
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc_info:
                await client.call_tool(
                    "ronin_msg_broadcast",
                    {"payload": {"body": "hi"}, "idempotency_key": "ik-broadcast-1"},
                )
            assert "PROD_WRITE_NOT_AUTHORIZED" in str(exc_info.value) or \
                "GATE_REQUIRES_PROD_WRITE" in str(exc_info.value)

    import asyncio
    asyncio.run(_run())


@pytest.mark.timeout(30)
def test_broadcast_allowed_with_prod_write(mcp_server_factory: Any, make_config: Any) -> None:
    """Broadcast succeeds with prod write enabled."""
    server = mcp_server_factory(make_config(prod_write=True))

    async def _run() -> None:
        async with Client(server) as client:
            result = await client.call_tool(
                "ronin_msg_broadcast",
                {"payload": {"body": "hi"}, "idempotency_key": "ik-broadcast-2"},
            )
            data = json.loads(_extract_text(result))
            assert "broadcast_id" in data

    import asyncio
    asyncio.run(_run())


@pytest.mark.timeout(30)
def test_gd_chatgroup_send_allowed(mcp_server_factory: Any, make_config: Any) -> None:
    """gd:-prefixed chatgroup send is allowed without prod write."""
    server = mcp_server_factory(make_config())

    async def _run() -> None:
        async with Client(server) as client:
            await client.call_tool(
                "ronin_chatgroup_create",
                {"channel_id": "chatgroup:gd:test-group", "display_name": "Test"},
            )
            result = await client.call_tool(
                "ronin_chatgroup_send",
                {
                    "channel_id": "chatgroup:gd:test-group",
                    "payload": {"body": "hi group"},
                    "idempotency_key": "ik-group-1",
                },
            )
            data = json.loads(_extract_text(result))
            assert "message_id" in data

    import asyncio
    asyncio.run(_run())


@pytest.mark.timeout(30)
def test_prod_chatgroup_send_rejected(mcp_server_factory: Any, make_config: Any) -> None:
    """Non-gd: chatgroup send is rejected without prod write."""
    server = mcp_server_factory(make_config(prod_write=True))

    async def _run() -> None:
        async with Client(server) as client:
            await client.call_tool(
                "ronin_chatgroup_create",
                {"channel_id": "chatgroup:prod-group", "display_name": "Prod"},
            )

    import asyncio
    asyncio.run(_run())

    # Now disable prod write and try to send
    server = mcp_server_factory(make_config())

    async def _run2() -> None:
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc_info:
                await client.call_tool(
                    "ronin_chatgroup_send",
                    {
                        "channel_id": "chatgroup:prod-group",
                        "payload": {"body": "hi"},
                        "idempotency_key": "ik-group-2",
                    },
                )
            assert "PROD_WRITE_NOT_AUTHORIZED" in str(exc_info.value)

    import asyncio
    asyncio.run(_run2())


@pytest.mark.timeout(30)
def test_wf_reindex_always_requires_prod_write(mcp_server_factory: Any, make_config: Any) -> None:
    """wf_reindex is a fleet-wide operation and always requires prod write."""
    server = mcp_server_factory(make_config())

    async def _run() -> None:
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc_info:
                await client.call_tool("ronin_wf_reindex", {"dry_run": True})
            assert "GATE_REQUIRES_PROD_WRITE" in str(exc_info.value)

    import asyncio
    asyncio.run(_run())


@pytest.mark.timeout(30)
def test_wf_reconcile_always_requires_prod_write(mcp_server_factory: Any, make_config: Any) -> None:
    """wf_reconcile is a fleet-wide operation and always requires prod write."""
    server = mcp_server_factory(make_config())

    async def _run() -> None:
        async with Client(server) as client:
            with pytest.raises(ToolError) as exc_info:
                await client.call_tool("ronin_wf_reconcile", {})
            assert "GATE_REQUIRES_PROD_WRITE" in str(exc_info.value)

    import asyncio
    asyncio.run(_run())
