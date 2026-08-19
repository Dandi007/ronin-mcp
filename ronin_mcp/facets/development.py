"""Facet 4: Development lifecycle (ronin_dev_*)."""

from __future__ import annotations

from typing import Any

from ronin_mcp.auth import WriteAuthError, check_write_auth
from ronin_mcp.backends.dev_dispatch import DevDispatchClient


def register(mcp: Any, *, controller: DevDispatchClient, auth_state: dict[str, Any]) -> None:
    @mcp.tool()
    def ronin_dev_list(
        state: str | None = None,
        repo: str | None = None,
        limit: int = 20,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """List developments."""
        params: dict[str, Any] = {"limit": limit}
        if state:
            params["state"] = state
        if repo:
            params["repo"] = repo
        if cursor:
            params["cursor"] = cursor
        return controller.get("/v1/developments", params=params)

    @mcp.tool()
    def ronin_dev_get(development_id: str) -> dict[str, Any]:
        """Get the full state of a development."""
        return controller.get(f"/v1/developments/{development_id}")

    @mcp.tool()
    def ronin_dev_events(
        development_id: str,
        after: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Get development events (incremental polling)."""
        params: dict[str, Any] = {"limit": limit}
        if after:
            params["after"] = after
        return controller.get(f"/v1/developments/{development_id}/events", params=params)

    @mcp.tool()
    def ronin_dev_evidence(development_id: str) -> dict[str, Any]:
        """Export the receipt/evidence chain."""
        return controller.get(f"/v1/developments/{development_id}/evidence")

    @mcp.tool()
    def ronin_dev_create(
        name: str,
        goal: str,
        idempotency_key: str,
        reason: str,
        initial_handoff: dict[str, Any],
        phase: str = "development",
        acceptance_commands: list[dict[str, Any]] | None = None,
        setup_commands: list[dict[str, Any]] | None = None,
        host_verify_commands: list[dict[str, Any]] | None = None,
        profile: str = "default",
        policy: str = "isolated-release-auto",
        work_folder: str | None = None,
        role_target_patch: dict[str, Any] | None = None,
        auto_start: bool = False,
        max_attempts: int | None = None,
    ) -> dict[str, Any]:
        """Create a development (requires gd: or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, name)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        body: dict[str, Any] = {
            "name": name,
            "goal": goal,
            "phase": phase,
            "profile": profile,
            "policy": policy,
            "idempotency_key": idempotency_key,
            "reason": reason,
            "initial_handoff": initial_handoff,
            "auto_start": auto_start,
        }
        if max_attempts is not None:
            body["max_attempts"] = max_attempts
        if acceptance_commands is not None:
            body["acceptance_commands"] = acceptance_commands
        if setup_commands is not None:
            body["setup_commands"] = setup_commands
        if host_verify_commands is not None:
            body["host_verify_commands"] = host_verify_commands
        if work_folder:
            body["work_folder"] = work_folder
        if role_target_patch is not None:
            body["role_target_patch"] = role_target_patch
        return controller.post("/v1/developments", body)

    @mcp.tool()
    def ronin_dev_start(
        development_id: str,
        idempotency_key: str,
        expected_revision: int,
        reason: str = "",
    ) -> dict[str, Any]:
        """Start a BOOTSTRAPPING development (requires gd: or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, development_id)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        return controller.post(
            f"/v1/developments/{development_id}/commands/start",
            {
                "idempotency_key": idempotency_key,
                "expected_revision": expected_revision,
                "reason": reason,
            },
        )

    @mcp.tool()
    def ronin_dev_steer(
        development_id: str,
        instruction: str,
        idempotency_key: str,
        expected_revision: int,
        reason: str = "",
        urgency: str = "next_safe_boundary",
    ) -> dict[str, Any]:
        """Inject a steering instruction (requires gd: or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, development_id)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        return controller.post(
            f"/v1/developments/{development_id}/commands/steer",
            {
                "idempotency_key": idempotency_key,
                "expected_revision": expected_revision,
                "reason": reason,
                "instruction": instruction,
                "urgency": urgency,
            },
        )

    @mcp.tool()
    def ronin_dev_reconfigure(
        development_id: str,
        idempotency_key: str,
        expected_revision: int,
        reason: str = "",
        profile: str | None = None,
        role_target_patch: dict[str, Any] | None = None,
        policy: str | None = None,
        acceptance_commands: list[dict[str, Any]] | None = None,
        setup_commands: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Reconfigure a development's profile/policy/commands (requires gd: or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, development_id)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        body: dict[str, Any] = {
            "idempotency_key": idempotency_key,
            "expected_revision": expected_revision,
            "reason": reason,
        }
        if profile:
            body["profile"] = profile
        if role_target_patch:
            body["role_target_patch"] = role_target_patch
        if policy:
            body["policy"] = policy
        if acceptance_commands is not None:
            body["acceptance_commands"] = acceptance_commands
        if setup_commands is not None:
            body["setup_commands"] = setup_commands
        return controller.post(
            f"/v1/developments/{development_id}/commands/reconfigure",
            body,
        )

    @mcp.tool()
    def ronin_dev_control(
        development_id: str,
        action: str,
        idempotency_key: str,
        expected_revision: int,
        reason: str = "",
    ) -> dict[str, Any]:
        """Pause/resume/cancel a development (requires gd: or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, development_id)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        return controller.post(
            f"/v1/developments/{development_id}/commands/control",
            {
                "idempotency_key": idempotency_key,
                "expected_revision": expected_revision,
                "reason": reason,
                "action": action,
            },
        )

    @mcp.tool()
    def ronin_dev_relock(
        development_id: str,
        plugin_commit: str,
        idempotency_key: str,
        expected_revision: int,
        reason: str = "",
    ) -> dict[str, Any]:
        """Relock a development to a new plugin commit (requires gd: or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, development_id)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        return controller.post(
            f"/v1/developments/{development_id}/commands/relock",
            {
                "idempotency_key": idempotency_key,
                "expected_revision": expected_revision,
                "reason": reason,
                "plugin_commit": plugin_commit,
            },
        )
