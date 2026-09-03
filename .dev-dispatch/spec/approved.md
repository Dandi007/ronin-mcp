# Ronin MCP dead tool removal

In the isolated worktree, remove the still-callable retired ronin MCP tool registrations for the 13 `ronin_dev_*`/`ronin_gate_*` tools and the 3 `ronin_pump_*` tools, following the wf-525fd4 M3 decision: remove them, do not redirect them. Remove only these dead tool surfaces and their now-obsolete active configuration references to the retired loop-engine controller and `/data/ronin/runs`; preserve live agent-bus/work-folder functionality, `/data/ronin/secrets`, active units, and historical documentation. Update focused tests and minimal docs as needed. All implementation and review must be dev-dispatch.

Acceptance:
```dd-acceptance
bash -lc 'set -eu; python -m pytest -q; python -c "from ronin_mcp.server import create_server; n={t.name for t in create_server().list_tools()}; r={\"ronin_dev_list\",\"ronin_dev_get\",\"ronin_dev_events\",\"ronin_dev_evidence\",\"ronin_dev_create\",\"ronin_dev_start\",\"ronin_dev_steer\",\"ronin_dev_reconfigure\",\"ronin_dev_control\",\"ronin_dev_relock\",\"ronin_gate_approve\",\"ronin_gate_reject\",\"ronin_pump_list\",\"ronin_pump_get\",\"ronin_pump_rounds\"}; assert n.isdisjoint(r); print(\"RONIN dead tool removal: PASS\")"'
```