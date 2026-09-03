# Ronin MCP (浪人 MCP)

Ronin MCP is an **aggregating façade** that exposes the ronin fleet's control
plane under a single `ronin_*` MCP namespace. It is the management console
for the ronin fleet, collapsing the control surfaces scattered across
agent-bus / work-folder into one MCP server bound to `127.0.0.1`.

## North star

Expose the ronin fleet's control plane through one MCP so any agent
(including the user) can drive it. The core demonstration surface is the
friend/group/message CRUD, plus work-folder file operations.

## Architecture

One MCP server, internally issuing HTTP calls to multiple backends:

| Backend | Protocol | Address | Purpose |
|---------|----------|---------|---------|
| agent-bus HTTP | HTTP REST | `http://127.0.0.1:7490` | alias / agent / channel / message / consume / ack |
| katana-work-folder MCP | MCP (streamable-http) | via MCP client | work folder / file ops |

The retired loop-engine Controller surface and the `/data/ronin/runs/` pump
reader were removed outright (wf-525fd4 M3 follow-up: remove, do not
redirect).

## Read/write separation

Read tools (`*_list`, `*_get`, `*_resolve`, `*_events`, `*_evidence`,
`*_whoami`, `*_search`, `*_stat`, `*_capabilities`, `*_read`, `*_read_bytes`)
are freely available to any authenticated caller.

Write tools are guarded at the entrance:

1. **Ephemeral mode** (`--ephemeral` / `RONIN_EPHEMERAL=1`): all writes
   routed to ephemeral backends; no restrictions.
2. **`gd:` prefix** (non-ephemeral): writes targeting `gd:` resources are
   allowed without explicit production authorization.
3. **Production writes** (non-`gd:`, non-ephemeral): require
   `RONIN_PROD_WRITE=1` / `--prod-write`; otherwise rejected with
   `PROD_WRITE_NOT_AUTHORIZED`.
4. **Fleet-wide / B-class operations** (`ronin_msg_broadcast`,
   `ronin_wf_reconcile`, `ronin_wf_reindex`) ALWAYS require
   `RONIN_PROD_WRITE=1`, even for `gd:` resources, because they are
   irreversible operations.

## Token red line

Credentials never enter argv / git / logs / model context. The agent-bus
gateway token is read from a 0600 file at
`/data/ronin/secrets/ronin-mcp.token` (or `RONIN_GATEWAY_TOKEN` env var
populated by systemd `EnvironmentFile=`). Tool parameters never carry
credentials; tool return values never include token material.

## Quickstart

```bash
# Install
uv sync --extra dev

# Run (ephemeral, no token required)
uv run python -m ronin_mcp.server --ephemeral

# Run (production, requires token)
RONIN_GATEWAY_TOKEN=$(cat /data/ronin/secrets/ronin-mcp.token) \
  uv run python -m ronin_mcp.server

# Tests
uv run --extra dev python -m pytest -q
```

## Tool surface (4 facets)

- **Friend (alias registry)**: `ronin_alias_*`, `ronin_agent_*`
- **Chatgroup**: `ronin_chatgroup_*`
- **Messaging**: `ronin_msg_*`, `ronin_inbox_*`
- **Work folder**: `ronin_wf_*`, `ronin_fs_*`

See `spec.md` (frozen contract) for the full tool list with parameters.
