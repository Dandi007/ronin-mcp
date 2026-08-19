"""Facet 3: Messaging (ronin_msg_* / ronin_inbox_*)."""

from __future__ import annotations

import secrets
import time
from typing import Any

from ronin_mcp.auth import WriteAuthError, check_write_auth
from ronin_mcp.backends.agent_bus import AgentBusClient, _BackendError


def _build_agent_msg_envelope(
    payload: dict[str, Any],
    *,
    from_alias: str | None,
    from_agent_id: str | None,
    bus: AgentBusClient,
    as_agent_id: str | None,
) -> dict[str, Any]:
    """Build an agent.msg.v1 payload envelope.

    The user ``payload`` carries at least ``body``; any envelope fields it
    already provides (``from_alias``, ``from_agent_id``, ``thread_id``,
    ``depth``, ``sent_at``) are preserved. Missing fields are defaulted:
    ``from_alias``/``from_agent_id`` are resolved from the ``from_alias``
    argument (alias lookup) or the delegated ``as_agent_id``; ``thread_id``
    and ``sent_at`` are generated; ``depth`` defaults to 0.
    """
    env: dict[str, Any] = dict(payload)
    resolved_from_alias = env.get("from_alias") or from_alias
    resolved_from_agent_id = env.get("from_agent_id") or from_agent_id
    if resolved_from_agent_id is None and resolved_from_alias is not None:
        try:
            record = bus.get(f"/v1/aliases/{resolved_from_alias}", as_agent_id=as_agent_id)
        except _BackendError:
            record = {}
        if isinstance(record, dict):
            resolved_from_agent_id = record.get("agent_id")
    if resolved_from_agent_id is None:
        # The publishing principal is the delegated agent (as_agent_id) or,
        # when no delegation is requested, the ronin-mcp gateway service.
        resolved_from_agent_id = as_agent_id or "mcp-gateway"
    env.setdefault("from_alias", resolved_from_alias or resolved_from_agent_id)
    env.setdefault("from_agent_id", resolved_from_agent_id)
    env.setdefault("thread_id", "ronin-" + secrets.token_hex(8))
    env.setdefault("depth", 0)
    env.setdefault("sent_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    return env


def register(mcp: Any, *, bus: AgentBusClient, auth_state: dict[str, Any]) -> None:
    @mcp.tool()
    def ronin_msg_send(
        alias: str,
        payload: dict[str, Any],
        idempotency_key: str,
        from_alias: str | None = None,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Send an agent.msg.v1 to an alias (requires gd: or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, alias)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        envelope = _build_agent_msg_envelope(
            payload, from_alias=from_alias, from_agent_id=None,
            bus=bus, as_agent_id=as_agent_id,
        )
        body: dict[str, Any] = {
            "kind": "agent.msg.v1",
            "payload": envelope,
            "idempotency_key": idempotency_key,
        }
        return bus.post(
            f"/v1/channels/agent:{alias}/publish",
            body,
            as_agent_id=as_agent_id,
        )

    @mcp.tool()
    def ronin_msg_broadcast(
        payload: dict[str, Any],
        idempotency_key: str,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Broadcast to online human principals (always requires RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, "broadcast", prod_write_required=True)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        return bus.post(
            "/v1/broadcast",
            {"payload": payload, "idempotency_key": idempotency_key},
            as_agent_id=as_agent_id,
        )

    @mcp.tool()
    def ronin_inbox_consume(
        alias: str | None = None,
        max_messages: int = 100,
        lease_ms: int | None = None,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Consume the inbox for self or a specified alias."""
        target = alias or (as_agent_id or "")
        try:
            check_write_auth(auth_state, target)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        body: dict[str, Any] = {"max_messages": max_messages}
        if lease_ms:
            body["lease_ms"] = lease_ms
        return bus.post(
            f"/v1/channels/agent:{target}/consume",
            body,
            as_agent_id=as_agent_id,
        )

    @mcp.tool()
    def ronin_inbox_ack(
        delivery_id: str,
        lease_token: str,
        result: dict[str, Any] | None = None,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Acknowledge a processed message."""
        body: dict[str, Any] = {"lease_token": lease_token}
        if result:
            body["result"] = result
        return bus.post(
            f"/v1/deliveries/{delivery_id}/ack",
            body,
            as_agent_id=as_agent_id,
        )

    @mcp.tool()
    def ronin_inbox_nack(
        delivery_id: str,
        lease_token: str,
        reason: str = "",
        retry_in_ms: int = 0,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Reject a message (may retry)."""
        body: dict[str, Any] = {
            "lease_token": lease_token,
            "reason": reason,
            "retry_in_ms": retry_in_ms,
        }
        return bus.post(
            f"/v1/deliveries/{delivery_id}/nack",
            body,
            as_agent_id=as_agent_id,
        )

    @mcp.tool()
    def ronin_inbox_renew(
        delivery_id: str,
        lease_token: str,
        lease_ms: int | None = None,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Renew a lease."""
        body: dict[str, Any] = {"lease_token": lease_token}
        if lease_ms:
            body["lease_ms"] = lease_ms
        return bus.post(
            f"/v1/deliveries/{delivery_id}/renew",
            body,
            as_agent_id=as_agent_id,
        )

    @mcp.tool()
    def ronin_msg_read(
        channel_id: str,
        after_seq: int = 0,
        kind: str | None = None,
        limit: int = 100,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Read channel message history."""
        params: dict[str, Any] = {"after_seq": after_seq, "limit": limit}
        if kind:
            params["kind"] = kind
        return bus.get(
            f"/v1/channels/{channel_id}/messages",
            params=params,
            as_agent_id=as_agent_id,
        )

    @mcp.tool()
    def ronin_msg_events(
        after: int = 0,
        channel_id: str | None = None,
        limit: int = 100,
        as_agent_id: str | None = None,
    ) -> dict[str, Any]:
        """Read the bus event stream."""
        params: dict[str, Any] = {"after": after, "limit": limit}
        if channel_id:
            params["channel_id"] = channel_id
        return bus.get("/v1/events", params=params, as_agent_id=as_agent_id)
