"""Facet 5: Work folder (ronin_wf_* / ronin_fs_*).

Proxies to the katana-work-folder MCP server. Write-surface tools apply the
``gd:`` / prod-write guardrail on the folder_id target.
"""

from __future__ import annotations

from typing import Any

from ronin_mcp.auth import WriteAuthError, check_write_auth
from ronin_mcp.backends.work_folder import WorkFolderClient


def register(mcp: Any, *, wf: WorkFolderClient, auth_state: dict[str, Any]) -> None:
    @mcp.tool()
    def ronin_wf_list(limit: int = 50) -> dict[str, Any]:
        """List active folders."""
        return wf.call("wf_list", {"limit": limit})

    @mcp.tool()
    def ronin_wf_create(topic: str, idempotency_key: str | None = None) -> dict[str, Any]:
        """Create a folder (requires gd: or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, topic)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        args: dict[str, Any] = {"topic": topic}
        if idempotency_key:
            args["idempotency_key"] = idempotency_key
        return wf.call("wf_create", args)

    @mcp.tool()
    def ronin_wf_resume(folder_id: str, idempotency_key: str | None = None) -> dict[str, Any]:
        """Resume a work state."""
        args: dict[str, Any] = {"folder_id": folder_id}
        if idempotency_key:
            args["idempotency_key"] = idempotency_key
        return wf.call("wf_resume", args)

    @mcp.tool()
    def ronin_wf_save(
        folder_id: str,
        summary: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Save a checkpoint (requires gd: or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, folder_id)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        args: dict[str, Any] = {"folder_id": folder_id}
        if summary:
            args["summary"] = summary
        if idempotency_key:
            args["idempotency_key"] = idempotency_key
        return wf.call("wf_save", args)

    @mcp.tool()
    def ronin_wf_search(query: str, top_k: int = 10) -> dict[str, Any]:
        """Search folders."""
        return wf.call("wf_search", {"query": query, "top_k": top_k})

    @mcp.tool()
    def ronin_wf_evidence_put(
        folder_id: str,
        filename: str,
        content: str,
        conclusion: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Write evidence (requires gd: or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, folder_id)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        args: dict[str, Any] = {"folder_id": folder_id, "filename": filename, "content": content}
        if conclusion:
            args["conclusion"] = conclusion
        if idempotency_key:
            args["idempotency_key"] = idempotency_key
        return wf.call("wf_evidence_put", args)

    @mcp.tool()
    def ronin_wf_evidence_migrate(
        folder_id: str,
        dry_run: bool = False,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Migrate evidence (requires gd: or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, folder_id)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        args: dict[str, Any] = {"folder_id": folder_id, "dry_run": dry_run}
        if idempotency_key:
            args["idempotency_key"] = idempotency_key
        return wf.call("wf_evidence_migrate", args)

    @mcp.tool()
    def ronin_wf_append_progress(
        folder_id: str,
        entry: dict[str, Any],
        source_session_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Append progress (requires gd: or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, folder_id)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        return wf.call(
            "wf_append_progress",
            {
                "folder_id": folder_id,
                "entry": entry,
                "source_session_id": source_session_id,
                "idempotency_key": idempotency_key,
            },
        )

    @mcp.tool()
    def ronin_wf_reconcile(
        scope_prefixes: list[str] | None = None,
        control_paths: list[str] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Safe recovery manifest (requires gd: or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, "reconcile")
        except WriteAuthError as exc:
            return exc.as_error_dict()
        args: dict[str, Any] = {}
        if scope_prefixes is not None:
            args["scope_prefixes"] = scope_prefixes
        if control_paths is not None:
            args["control_paths"] = control_paths
        if idempotency_key:
            args["idempotency_key"] = idempotency_key
        return wf.call("wf_reconcile", args)

    @mcp.tool()
    def ronin_wf_reindex(dry_run: bool = False, idempotency_key: str | None = None) -> dict[str, Any]:
        """Rebuild the INDEX (requires gd: or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, "reindex")
        except WriteAuthError as exc:
            return exc.as_error_dict()
        args: dict[str, Any] = {"dry_run": dry_run}
        if idempotency_key:
            args["idempotency_key"] = idempotency_key
        return wf.call("wf_reindex", args)

    @mcp.tool()
    def ronin_fs_list(folder_id: str, dirname: str | None = None) -> dict[str, Any]:
        """List a directory."""
        args: dict[str, Any] = {"folder_id": folder_id}
        if dirname:
            args["dirname"] = dirname
        return wf.call("fs_list", args)

    @mcp.tool()
    def ronin_fs_read(
        folder_id: str,
        filename: str,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Read a file."""
        args: dict[str, Any] = {"folder_id": folder_id, "filename": filename}
        if limit is not None:
            args["limit"] = limit
        if offset is not None:
            args["offset"] = offset
        return wf.call("fs_read", args)

    @mcp.tool()
    def ronin_fs_read_bytes(
        folder_id: str,
        filename: str,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Read binary."""
        args: dict[str, Any] = {"folder_id": folder_id, "filename": filename}
        if limit is not None:
            args["limit"] = limit
        if offset is not None:
            args["offset"] = offset
        return wf.call("fs_read_bytes", args)

    @mcp.tool()
    def ronin_fs_stat(folder_id: str, filename: str) -> dict[str, Any]:
        """File status."""
        return wf.call("fs_stat", {"folder_id": folder_id, "filename": filename})

    @mcp.tool()
    def ronin_fs_resolve(folder_id: str, filename: str | None = None) -> dict[str, Any]:
        """Resolve a brief."""
        args: dict[str, Any] = {"folder_id": folder_id}
        if filename:
            args["filename"] = filename
        return wf.call("fs_resolve", args)

    @mcp.tool()
    def ronin_fs_create(
        folder_id: str,
        filename: str,
        content: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Create a file (requires gd: or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, folder_id)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        args: dict[str, Any] = {"folder_id": folder_id, "filename": filename, "content": content}
        if idempotency_key:
            args["idempotency_key"] = idempotency_key
        return wf.call("fs_create", args)

    @mcp.tool()
    def ronin_fs_write(
        folder_id: str,
        filename: str,
        content: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Write a file (requires gd: or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, folder_id)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        args: dict[str, Any] = {"folder_id": folder_id, "filename": filename, "content": content}
        if idempotency_key:
            args["idempotency_key"] = idempotency_key
        return wf.call("fs_write", args)

    @mcp.tool()
    def ronin_fs_edit(
        folder_id: str,
        filename: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Edit a file (requires gd: or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, folder_id)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        args: dict[str, Any] = {
            "folder_id": folder_id,
            "filename": filename,
            "old_string": old_string,
            "new_string": new_string,
            "replace_all": replace_all,
        }
        if idempotency_key:
            args["idempotency_key"] = idempotency_key
        return wf.call("fs_edit", args)

    @mcp.tool()
    def ronin_fs_delete(
        folder_id: str,
        filename: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Delete a file (requires gd: or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, folder_id)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        args: dict[str, Any] = {"folder_id": folder_id, "filename": filename}
        if idempotency_key:
            args["idempotency_key"] = idempotency_key
        return wf.call("fs_delete", args)

    @mcp.tool()
    def ronin_fs_copy(
        source_folder_id: str,
        source_filename: str,
        dest_folder_id: str,
        dest_filename: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Copy a file (requires gd: or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, dest_folder_id)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        args: dict[str, Any] = {
            "source_folder_id": source_folder_id,
            "source_filename": source_filename,
            "dest_folder_id": dest_folder_id,
            "dest_filename": dest_filename,
        }
        if idempotency_key:
            args["idempotency_key"] = idempotency_key
        return wf.call("fs_copy", args)

    @mcp.tool()
    def ronin_fs_rename(
        source_folder_id: str,
        source_filename: str,
        dest_folder_id: str,
        dest_filename: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Rename a file (requires gd: or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, dest_folder_id)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        args: dict[str, Any] = {
            "source_folder_id": source_folder_id,
            "source_filename": source_filename,
            "dest_folder_id": dest_folder_id,
            "dest_filename": dest_filename,
        }
        if idempotency_key:
            args["idempotency_key"] = idempotency_key
        return wf.call("fs_rename", args)

    @mcp.tool()
    def ronin_fs_batch(
        folder_id: str,
        operations: list[dict[str, Any]],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Batch operations (requires gd: or RONIN_PROD_WRITE=1)."""
        try:
            check_write_auth(auth_state, folder_id)
        except WriteAuthError as exc:
            return exc.as_error_dict()
        args: dict[str, Any] = {"folder_id": folder_id, "operations": operations}
        if idempotency_key:
            args["idempotency_key"] = idempotency_key
        return wf.call("fs_batch", args)

    @mcp.tool()
    def ronin_fs_capabilities() -> dict[str, Any]:
        """List capabilities."""
        return wf.call("fs_capabilities", {})
