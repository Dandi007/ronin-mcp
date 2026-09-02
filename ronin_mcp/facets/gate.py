"""Gate-approval facet (B-class irreversible operations).

ronin_gate_approve / ronin_gate_reject ALWAYS require
RONIN_PROD_WRITE=1, even for gd:-prefixed developments, because gate
approvals are irreversible. This prevents accidentally approving a
real gate from a test flow.
"""

from __future__ import annotations

from typing import Any

from ronin_mcp.auth import AuthState, check_write_auth
from ronin_mcp.backends.dev_dispatch import DevDispatchClient


def register(
    mcp: Any,
    auth: AuthState,
    controller: DevDispatchClient,
    error_wrapper: Any,
) -> None:
    """Register ronin_gate_* tools on the FastMCP server."""

    @mcp.tool()
    def ronin_gate_approve(
        development_id: str,
        gate_id: str,
        idempotency_key: str,
        expected_revision: int,
        operator_identity: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """Approve a gate (write; ALWAYS requires RONIN_PROD_WRITE=1)."""
        def _do() -> dict[str, Any]:
            check_write_auth(auth, development_id, prod_write_required=True)
            return controller.post(
                f"/v1/developments/{development_id}/commands/gate",
                {
                    "idempotency_key": idempotency_key,
                    "expected_revision": expected_revision,
                    "reason": reason,
                    "gate_id": gate_id,
                    "decision": "approve",
                    "operator_identity": operator_identity,
                },
                as_agent_id=operator_identity,
            )
        return error_wrapper(_do)

    @mcp.tool()
    def ronin_gate_reject(
        development_id: str,
        gate_id: str,
        idempotency_key: str,
        expected_revision: int,
        operator_identity: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """Reject a gate (write; ALWAYS requires RONIN_PROD_WRITE=1)."""
        def _do() -> dict[str, Any]:
            check_write_auth(auth, development_id, prod_write_required=True)
            return controller.post(
                f"/v1/developments/{development_id}/commands/gate",
                {
                    "idempotency_key": idempotency_key,
                    "expected_revision": expected_revision,
                    "reason": reason,
                    "gate_id": gate_id,
                    "decision": "reject",
                    "operator_identity": operator_identity,
                },
                as_agent_id=operator_identity,
            )
        return error_wrapper(_do)
