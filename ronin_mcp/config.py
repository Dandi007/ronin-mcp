"""Configuration management for Ronin MCP.

Token material is read from a 0600 file and never enters argv, git, logs,
or model context. The gateway token is injected into the agent-bus HTTP
client at startup; tool parameters never carry credentials.
"""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "ronin" / "config.yaml"

DEFAULT_CONFIG: dict[str, Any] = {
    "server": {
        "host": "127.0.0.1",
        "port": 5609,
    },
    "backends": {
        "agent_bus": {
            "url": "http://127.0.0.1:7490",
            "gateway_token_file": "/data/ronin/secrets/ronin-mcp.token",
        },
        "work_folder": {
            "mcp_url": "http://127.0.0.1:5605/mcp",
        },
    },
    "auth": {
        "prod_write_enabled": False,
        "ephemeral": False,
    },
}


def load_config(config_path: str | None = None) -> dict[str, Any]:
    """Load config from YAML, deep-merged over DEFAULT_CONFIG.

    Environment overrides:
      RONIN_MCP_CONFIG  -> config file path
      RONIN_EPHEMERAL=1 -> auth.ephemeral = True
      RONIN_PROD_WRITE=1 -> auth.prod_write_enabled = True
    """
    path = config_path or os.environ.get("RONIN_MCP_CONFIG", str(DEFAULT_CONFIG_PATH))
    loaded: dict[str, Any] = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}

    config = _deep_merge(DEFAULT_CONFIG, loaded)

    if os.environ.get("RONIN_EPHEMERAL") == "1":
        config["auth"]["ephemeral"] = True
    if os.environ.get("RONIN_PROD_WRITE") == "1":
        config["auth"]["prod_write_enabled"] = True

    return config


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_gateway_token(path: str) -> str:
    """Read token from file. Never logs, never enters argv.

    The file must be at least 32 characters; shorter tokens are rejected
    to prevent accidental weak credentials.
    """
    with open(path, "r", encoding="utf-8") as f:
        token = f.read().strip()
    if len(token) < 32:
        raise ValueError(f"Gateway token in {path} too short (min 32 chars)")
    return token


def resolve_gateway_token(config: dict[str, Any]) -> str:
    """Resolve the agent-bus gateway token from config or env.

    Priority:
      1. RONIN_GATEWAY_TOKEN env var (for systemd EnvironmentFile)
      2. gateway_token_file from config
    Returns empty string when neither is available (ephemeral mode).
    """
    env_token = os.environ.get("RONIN_GATEWAY_TOKEN") or os.environ.get("BUS_GATEWAY_TOKEN")
    if env_token and len(env_token) >= 32:
        return env_token

    token_file = config.get("backends", {}).get("agent_bus", {}).get("gateway_token_file", "")
    if token_file and os.path.exists(token_file):
        return load_gateway_token(token_file)

    return ""
