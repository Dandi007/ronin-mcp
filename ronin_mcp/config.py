"""Configuration management for Ronin MCP.

Loads a YAML config, deep-merges over defaults, and reads the agent-bus
gateway token from a 0600 file. Token material never enters argv, model
context, or logs.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "ronin-mcp" / "config.yaml"

DEFAULT_CONFIG: dict[str, Any] = {
    "schema_version": 1,
    "server": {
        "host": "127.0.0.1",
        "port": 5609,
    },
    "backends": {
        "agent_bus": {
            "url": "http://127.0.0.1:7490",
            "gateway_token_file": "/data/ronin/secrets/ronin-mcp.token",
        },
        "dev_dispatch": {
            "url": "http://127.0.0.1:7460",
        },
        "work_folder": {
            "mcp_url": "http://127.0.0.1:5605/mcp",
        },
        "pump_state": {
            "runs_root": "/data/ronin/runs",
        },
    },
    "auth": {
        "prod_write_enabled": False,
        "ephemeral": False,
    },
}


def load_config(config_path: str | None = None) -> dict[str, Any]:
    path = config_path or os.environ.get("RONIN_MCP_CONFIG", str(DEFAULT_CONFIG_PATH))
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
    else:
        loaded = {}
    return _deep_merge(DEFAULT_CONFIG, loaded)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    import copy

    result: dict[str, Any] = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_gateway_token(path: str) -> str:
    """Read token from file. Never logs, never enters argv."""
    with open(path, "r", encoding="utf-8") as f:
        token = f.read().strip()
    if len(token) < 32:
        raise ValueError(f"Gateway token in {path} too short (min 32 chars)")
    return token


def resolve_auth_state(config: dict[str, Any]) -> dict[str, Any]:
    """Compute the effective auth state from config + environment.

    Precedence: explicit CLI/env wins over config. ``RONIN_EPHEMERAL=1`` and
    ``RONIN_PROD_WRITE=1`` map to the ephemeral / prod_write flags.
    """
    auth_cfg = config.get("auth", {})
    ephemeral = bool(auth_cfg.get("ephemeral", False)) or os.environ.get("RONIN_EPHEMERAL") == "1"
    prod_write = (
        bool(auth_cfg.get("prod_write_enabled", False))
        or os.environ.get("RONIN_PROD_WRITE") == "1"
    )
    return {"ephemeral": ephemeral, "prod_write_enabled": prod_write}
