"""Facet 7: Gate approval (ronin_gate_*).

Gate approve/reject are B-class irreversible operations and always require
``RONIN_PROD_WRITE=1``, even for ``gd:`` developments.
"""

from __future__ import annotations

from typing import Any

from ronin_mcp.auth import WriteAuthError, check_write_auth
from ronin_mcp.backends.dev_dispatch import DevDispatchClient


def register(mcp: Any, *, controller: DevDispatchClient, auth_state: dict[str, Any]) -> None:
    def _gate(
        development_id: str,
        gate_id: str,
        idempotency_key: str,
        expected_revision: int,
        operator_identity: str,
        decision: str,
        reason: str = "",
    ) -> dict[str, Any]:
        try:
            check_write_auth(auth_state, development_id, prod_write_required=True)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        return controller.post(
            f"/v1/developments/{development_id}/commands/gate",
            {
                "idempotency_key": idempotency_key,
                "expected_revision": expected_revision,
                "reason": reason,
                "gate_id": gate_id,
                "decision": decision,
                "operator_identity": operator_identity,
            },
            operator_identity=operator_identity,
        )

    @mcp.tool()
    def ronin_gate_approve(
        development_id: str,
        gate_id: str,
        idempotency_key: str,
        expected_revision: int,
        operator_identity: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """Approve a gate (always requires RONIN_PROD_WRITE=1)."""
        return _gate(
            development_id,
            gate_id,
            idempotency_key,
            expected_revision,
            operator_identity,
            "approve",
            reason,
        )

    @mcp.tool()
    def ronin_gate_reject(
        development_id: str,
        gate_id: str,
        idempotency_key: str,
        expected_revision: int,
        operator_identity: str,
        reason: str = "",
    ) -> dict[str, Any]:
        """Reject a gate (always requires RONIN_PROD_WRITE=1)."""
        return _gate(
            development_id,
            gate_id,
            idempotency_key,
            expected_revision,
            operator_identity,
            "reject",
            reason,
        )
