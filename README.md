# Ronin MCP (浪人 MCP)

Ronin MCP is the **aggregating façade** for the ronin fleet's control plane.
It exposes a single MCP server (`ronin_*` namespace) over four backends:

- **agent-bus HTTP** — alias / agent / channel / message / consume / ack
- **loop-engine Controller HTTP** — development CRUD / gate / steer / control
- **katana-work-folder MCP** — work folder / file ops (via MCP client)
- **filesystem** (`/data/ronin/runs/`) — pump run state (read-only)

## Trust boundary & write guardrails

Read-surface tools are free. Every write-surface tool is guarded at the
entrance:

1. **Ephemeral mode** (`--ephemeral` / `RONIN_EPHEMERAL=1`) — all writes open.
2. **`gd:` prefix** — test/dev namespace, allowed without extra auth.
3. **Production write** — requires `RONIN_PROD_WRITE=1` / `--prod-write`.
4. **Gate approve/reject** — B-class irreversible, **always** require prod
   write even for `gd:` developments.

Token material never enters argv, model context, or logs. `ronin-mcp`
delegates on behalf of agents via `X-Bus-On-Behalf-Of` / `X-Operator-Identity`,
reading the bus gateway token from a 0600 file.

## Quickstart

```bash
uv sync --extra dev
# start the gateway (needs agent-bus + controller reachable)
uv run python -m ronin_mcp.server
# or with a config file:
uv run python -m ronin_mcp.server --config config/config.yaml.example
```

Bind address defaults to `127.0.0.1:5609`, transport `streamable-http` at
`/mcp`.

## Tests

```bash
uv run python -m pytest -q
```
