"""Write-side guardrails for Ronin MCP.

Rules (in priority order, see spec §判据 1):
  1. Ephemeral mode: all writes allowed (routed to ephemeral backends).
  2. gd: prefix: write operations targeting gd: resources are allowed.
  3. Production writes (non-gd:, non-ephemeral): require explicit
     RONIN_PROD_WRITE=1 / --prod-write; otherwise rejected with
     PROD_WRITE_NOT_AUTHORIZED.
  4. Gate approvals (ronin_gate_approve / ronin_gate_reject) ALWAYS require
     prod write authorization, even for gd: developments, because gate
     approval is a B-class irreversible operation.
  5. ronin_dev_create targeting a production repo requires prod write
     authorization (the repo URL itself is the prod-write target).

AuthState is a small carrier so facets can share the same boolean flags
without re-reading environment on every tool call.
"""

from __future__ import annotations

from dataclasses import dataclass


PROD_WRITE_NOT_AUTHORIZED_ERROR = {
    "code": "PROD_WRITE_NOT_AUTHORIZED",
    "message": (
        "Production write requires RONIN_PROD_WRITE=1 or --prod-write. "
        "Use gd: prefix for test resources."
    ),
    "details": {"retryable": False},
}

GATE_REQUIRES_PROD_WRITE_ERROR = {
    "code": "GATE_REQUIRES_PROD_WRITE",
    "message": (
        "Gate approvals require RONIN_PROD_WRITE=1 or --prod-write; "
        "they are B-class irreversible operations and cannot be authorized "
        "by the gd: prefix alone."
    ),
    "details": {"retryable": False},
}


class WriteAuthError(Exception):
    """Raised when a write operation is not authorized.

    Carries the canonical error payload so the server layer can surface
    it to the caller as a structured MCP error.
    """

    def __init__(self, payload: dict[str, object]) -> None:
        super().__init__(str(payload.get("code", "WRITE_AUTH_ERROR")))
        self.payload = payload


@dataclass
class AuthState:
    """Snapshot of write-authorization flags for one server build."""

    prod_write_enabled: bool
    ephemeral: bool

    @classmethod
    def from_config(cls, config: dict[str, object]) -> "AuthState":
        auth_cfg = config.get("auth", {}) if isinstance(config, dict) else {}
        return cls(
            prod_write_enabled=bool(auth_cfg.get("prod_write_enabled", False)),
            ephemeral=bool(auth_cfg.get("ephemeral", False)),
        )


def _is_gd_prefixed(target: str) -> bool:
    """A target is gd:-prefixed when it starts with 'gd:' (case-sensitive)."""
    return isinstance(target, str) and target.startswith("gd:")


def check_write_auth(
    auth: AuthState,
    target: str,
    prod_write_required: bool = False,
) -> None:
    """Authorize a write operation against the target resource.

    Args:
        auth: server-level AuthState (prod_write_enabled / ephemeral).
        target: the resource identifier the write touches (alias,
            agent_id, channel_id, work_folder, repo URL, development_id).
        prod_write_required: True for operations that always need prod
            authorization regardless of gd: prefix (gate approve/reject,
            dev_create against production repos).

    Raises:
        WriteAuthError: when the write is not authorized.
    """
    if auth.ephemeral:
        return

    if prod_write_required:
        if auth.prod_write_enabled:
            return
        raise WriteAuthError(GATE_REQUIRES_PROD_WRITE_ERROR)

    if _is_gd_prefixed(target):
        return

    if auth.prod_write_enabled:
        return

    raise WriteAuthError(PROD_WRITE_NOT_AUTHORIZED_ERROR)
