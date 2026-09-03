# ronin-mcp dead tool removal

Implement and review only in the isolated git worktree. Never modify the production checkout. Never delete tests.

## Hard constraints

1. Remove the 13 dead `ronin_dev_*` / `ronin_gate_*` tools and the 3 dead `ronin_pump_*` tools. The exact dead names are: `ronin_dev_list`, `ronin_dev_get`, `ronin_dev_events`, `ronin_dev_evidence`, `ronin_dev_create`, `ronin_dev_start`, `ronin_dev_steer`, `ronin_dev_reconfigure`, `ronin_dev_control`, `ronin_dev_relock`, `ronin_gate_approve`, `ronin_gate_reject`, `ronin_pump_list`, `ronin_pump_get`, `ronin_pump_rounds`. No tool with any of the prefixes `ronin_dev_`, `ronin_gate_`, or `ronin_pump_` may remain registered.
2. Zero test deletion: rewrite, not delete, `tests/test_development.py`, `tests/test_gate.py`, and `tests/test_pump.py` so they assert these dead tools are absent from `create_server().list_tools()`. All three files must remain regular files.

## Acceptance

`python -m pytest -q` must be fully green. The three named test files must exist. The dead-name set must be disjoint from the `create_server().list_tools()` registry. The acceptance must print `RONIN dead tool removal: PASS` after these checks.

```dd-acceptance
python -m pytest -q
python -c "from pathlib import Path; from ronin_mcp.server import create_server; required = [Path('tests/test_development.py'), Path('tests/test_gate.py'), Path('tests/test_pump.py')]; assert all(p.is_file() for p in required), 'required test files must be retained'; registered = {t.name for t in create_server().list_tools()}; dead = {'ronin_dev_list','ronin_dev_get','ronin_dev_events','ronin_dev_evidence','ronin_dev_create','ronin_dev_start','ronin_dev_steer','ronin_dev_reconfigure','ronin_dev_control','ronin_dev_relock','ronin_gate_approve','ronin_gate_reject','ronin_pump_list','ronin_pump_get','ronin_pump_rounds'}; assert registered.isdisjoint(dead); assert not any(name.startswith(('ronin_dev_','ronin_gate_','ronin_pump_')) for name in registered); print('RONIN dead tool removal: PASS')"
```