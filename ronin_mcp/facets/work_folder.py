"""Work-folder facet (katana-work-folder MCP passthrough).

ronin_wf_* and ronin_fs_* map 1:1 to the underlying katana-work-folder
MCP tools. Write operations are guarded by check_write_auth on the
folder_id (or topic for wf_create).
"""

from __future__ import annotations

from typing import Any

from ronin_mcp.auth import AuthState, check_write_auth
from ronin_mcp.backends.work_folder import WorkFolderClient


def register(
    mcp: Any,
    auth: AuthState,
    work_folder: WorkFolderClient,
    error_wrapper: Any,
) -> None:
    """Register ronin_wf_* and ronin_fs_* tools on the FastMCP server."""

    @mcp.tool()
    async def ronin_wf_list(limit: int = 10) -> dict[str, Any]:
        """List active folders (read)."""
        return await _wrap(work_folder, error_wrapper, "wf_list", {"limit": limit})

    @mcp.tool()
    async def ronin_wf_create(
        topic: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Create a folder (write; gd: prefix or RONIN_PROD_WRITE=1)."""
        check_write_auth(auth, topic)
        return await _wrap(
            work_folder,
            error_wrapper,
            "wf_create",
            {"topic": topic, "idempotency_key": idempotency_key},
        )

    @mcp.tool()
    async def ronin_wf_resume(
        folder_id: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Resume a folder's working state (read)."""
        return await _wrap(
            work_folder,
            error_wrapper,
            "wf_resume",
            {"folder_id": folder_id, "idempotency_key": idempotency_key},
        )

    @mcp.tool()
    async def ronin_wf_save(
        folder_id: str,
        summary: str = "checkpoint",
        context_snapshot: str | None = None,
        resume_fields: dict[str, Any] | None = None,
        golden_order_additions: str | None = None,
        findings_addition: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Save a checkpoint (write; gd: prefix or RONIN_PROD_WRITE=1)."""
        check_write_auth(auth, folder_id)
        args: dict[str, Any] = {
            "folder_id": folder_id,
            "summary": summary,
            "idempotency_key": idempotency_key,
        }
        if context_snapshot is not None:
            args["context_snapshot"] = context_snapshot
        if resume_fields is not None:
            args["resume_fields"] = resume_fields
        if golden_order_additions is not None:
            args["golden_order_additions"] = golden_order_additions
        if findings_addition is not None:
            args["findings_addition"] = findings_addition
        return await _wrap(work_folder, error_wrapper, "wf_save", args)

    @mcp.tool()
    async def ronin_wf_search(query: str, top_k: int = 10) -> dict[str, Any]:
        """Search folders (read)."""
        return await _wrap(
            work_folder, error_wrapper, "wf_search", {"query": query, "top_k": top_k}
        )

    @mcp.tool()
    async def ronin_wf_evidence_put(
        folder_id: str,
        filename: str,
        content: str,
        conclusion: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Write evidence (write; gd: prefix or RONIN_PROD_WRITE=1)."""
        check_write_auth(auth, folder_id)
        args: dict[str, Any] = {
            "folder_id": folder_id,
            "filename": filename,
            "content": content,
            "idempotency_key": idempotency_key,
        }
        if conclusion is not None:
            args["conclusion"] = conclusion
        return await _wrap(work_folder, error_wrapper, "wf_evidence_put", args)

    @mcp.tool()
    async def ronin_wf_evidence_migrate(
        folder_id: str,
        dry_run: bool = False,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Migrate evidence (write; gd: prefix or RONIN_PROD_WRITE=1)."""
        check_write_auth(auth, folder_id)
        return await _wrap(
            work_folder,
            error_wrapper,
            "wf_evidence_migrate",
            {
                "folder_id": folder_id,
                "dry_run": dry_run,
                "idempotency_key": idempotency_key,
            },
        )

    @mcp.tool()
    async def ronin_wf_append_progress(
        folder_id: str,
        entry: str,
        source_session_id: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """Append progress (write; gd: prefix or RONIN_PROD_WRITE=1)."""
        check_write_auth(auth, folder_id)
        return await _wrap(
            work_folder,
            error_wrapper,
            "wf_append_progress",
            {
                "folder_id": folder_id,
                "entry": entry,
                "source_session_id": source_session_id,
                "idempotency_key": idempotency_key,
            },
        )

    @mcp.tool()
    async def ronin_wf_reconcile(
        scope_prefixes: list[str] | None = None,
        control_paths: list[str] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Safe recovery checklist (write; always requires RONIN_PROD_WRITE=1)."""
        check_write_auth(auth, "reconcile", prod_write_required=True)
        args: dict[str, Any] = {"idempotency_key": idempotency_key}
        if scope_prefixes is not None:
            args["scope_prefixes"] = scope_prefixes
        if control_paths is not None:
            args["control_paths"] = control_paths
        return await _wrap(work_folder, error_wrapper, "wf_reconcile", args)

    @mcp.tool()
    async def ronin_wf_reindex(
        dry_run: bool = False,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Rebuild INDEX (write; always requires RONIN_PROD_WRITE=1)."""
        check_write_auth(auth, "reindex", prod_write_required=True)
        return await _wrap(
            work_folder,
            error_wrapper,
            "wf_reindex",
            {"dry_run": dry_run, "idempotency_key": idempotency_key},
        )

    @mcp.tool()
    async def ronin_fs_list(folder_id: str, dirname: str = "") -> dict[str, Any]:
        """List a directory (read)."""
        return await _wrap(
            work_folder, error_wrapper, "fs_list", {"folder_id": folder_id, "dirname": dirname}
        )

    @mcp.tool()
    async def ronin_fs_read(
        folder_id: str,
        filename: str,
        limit: int | None = None,
        offset: int | None = None,
    ) -> dict[str, Any]:
        """Read a file (read)."""
        args: dict[str, Any] = {"folder_id": folder_id, "filename": filename}
        if limit is not None:
            args["limit"] = limit
        if offset is not None:
            args["offset"] = offset
        return await _wrap(work_folder, error_wrapper, "fs_read", args)

    @mcp.tool()
    async def ronin_fs_read_bytes(
        folder_id: str,
        filename: str,
        limit: int = 262144,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Read bytes (read)."""
        return await _wrap(
            work_folder,
            error_wrapper,
            "fs_read_bytes",
            {"folder_id": folder_id, "filename": filename, "limit": limit, "offset": offset},
        )

    @mcp.tool()
    async def ronin_fs_stat(folder_id: str, filename: str) -> dict[str, Any]:
        """File stat (read)."""
        return await _wrap(
            work_folder, error_wrapper, "fs_stat", {"folder_id": folder_id, "filename": filename}
        )

    @mcp.tool()
    async def ronin_fs_resolve(
        folder_id: str,
        filename: str = "_brief.md",
    ) -> dict[str, Any]:
        """Resolve a brief (read)."""
        return await _wrap(
            work_folder,
            error_wrapper,
            "fs_resolve",
            {"folder_id": folder_id, "filename": filename},
        )

    @mcp.tool()
    async def ronin_fs_create(
        folder_id: str,
        filename: str,
        content: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Create a file (write; gd: prefix or RONIN_PROD_WRITE=1)."""
        check_write_auth(auth, folder_id)
        return await _wrap(
            work_folder,
            error_wrapper,
            "fs_create",
            {
                "folder_id": folder_id,
                "filename": filename,
                "content": content,
                "idempotency_key": idempotency_key,
            },
        )

    @mcp.tool()
    async def ronin_fs_write(
        folder_id: str,
        filename: str,
        content: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Write a file (write; gd: prefix or RONIN_PROD_WRITE=1)."""
        check_write_auth(auth, folder_id)
        return await _wrap(
            work_folder,
            error_wrapper,
            "fs_write",
            {
                "folder_id": folder_id,
                "filename": filename,
                "content": content,
                "idempotency_key": idempotency_key,
            },
        )

    @mcp.tool()
    async def ronin_fs_edit(
        folder_id: str,
        filename: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Edit a file (write; gd: prefix or RONIN_PROD_WRITE=1)."""
        check_write_auth(auth, folder_id)
        return await _wrap(
            work_folder,
            error_wrapper,
            "fs_edit",
            {
                "folder_id": folder_id,
                "filename": filename,
                "old_string": old_string,
                "new_string": new_string,
                "replace_all": replace_all,
                "idempotency_key": idempotency_key,
            },
        )

    @mcp.tool()
    async def ronin_fs_delete(
        folder_id: str,
        filename: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Delete a file (write; gd: prefix or RONIN_PROD_WRITE=1)."""
        check_write_auth(auth, folder_id)
        return await _wrap(
            work_folder,
            error_wrapper,
            "fs_delete",
            {
                "folder_id": folder_id,
                "filename": filename,
                "idempotency_key": idempotency_key,
            },
        )

    @mcp.tool()
    async def ronin_fs_copy(
        source_folder_id: str,
        source_filename: str,
        dest_folder_id: str,
        dest_filename: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Copy a file (write; gd: prefix or RONIN_PROD_WRITE=1)."""
        check_write_auth(auth, dest_folder_id)
        return await _wrap(
            work_folder,
            error_wrapper,
            "fs_copy",
            {
                "source_folder_id": source_folder_id,
                "source_filename": source_filename,
                "dest_folder_id": dest_folder_id,
                "dest_filename": dest_filename,
                "idempotency_key": idempotency_key,
            },
        )

    @mcp.tool()
    async def ronin_fs_rename(
        source_folder_id: str,
        source_filename: str,
        dest_folder_id: str,
        dest_filename: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Rename a file (write; gd: prefix or RONIN_PROD_WRITE=1)."""
        check_write_auth(auth, dest_folder_id)
        return await _wrap(
            work_folder,
            error_wrapper,
            "fs_rename",
            {
                "source_folder_id": source_folder_id,
                "source_filename": source_filename,
                "dest_folder_id": dest_folder_id,
                "dest_filename": dest_filename,
                "idempotency_key": idempotency_key,
            },
        )

    @mcp.tool()
    async def ronin_fs_batch(
        folder_id: str,
        operations: list[dict[str, Any]],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Batch operations (write; gd: prefix or RONIN_PROD_WRITE=1)."""
        check_write_auth(auth, folder_id)
        return await _wrap(
            work_folder,
            error_wrapper,
            "fs_batch",
            {
                "folder_id": folder_id,
                "operations": operations,
                "idempotency_key": idempotency_key,
            },
        )

    @mcp.tool()
    async def ronin_fs_capabilities() -> dict[str, Any]:
        """List capabilities (read)."""
        return await _wrap(work_folder, error_wrapper, "fs_capabilities", {})


async def _wrap(
    work_folder: WorkFolderClient,
    error_wrapper: Any,
    tool_name: str,
    arguments: dict[str, Any],
) -> Any:
    def _call() -> Any:
        return work_folder.call_sync(tool_name, arguments)

    return error_wrapper(_call)
