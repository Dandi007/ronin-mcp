# ronin-mcp 仓侧 /metrics 接入（观测前置）

## 背景与缺口（真机 2026-08-30）
- ronin-mcp（Python/fastmcp，`/data/code/self/ronin-mcp`，`ronin_mcp` 包，systemd `ronin-mcp.service` 监听 `127.0.0.1:5609`）是「浪人舰队控制面聚合门面」——聚合 agent-bus/loop-engine/katana-work-folder/pump state 七 facet 到单一 `ronin_*` MCP 命名空间（build_mcp_server，`mcp.run(transport="streamable-http", path="/mcp")`）。
- 生产常驻（M×H 控制面），但 `:5609` 无 `/metrics`（`/`、`/metrics`、`/health` 均 404）→ 存活无监控。

## 交付
1. 新增 **process-local `/metrics`** 端点，返回 Prometheus text：`# TYPE ronin_mcp_up gauge` + `ronin_mcp_up 1`；content-type `text/plain; version=0.0.4; charset=utf-8`；免鉴权，**绝不触碰任何 backend/facet**（agent-bus/loop-engine/katana/pump 不探测）。
2. 实现方式：fastmcp `streamable-http` 底层 ASGI 为 starlette——在 `build_mcp_server` 产出的 ASGI app（`mcp.http_app()` 或等价）上挂 `/metrics` 路由（纯 Starlette 文本响应，不 import 重 backend）；保持 `/mcp` 与其余 facet 路由语义不变。
3. 测试 `tests/test_metrics.py`：用 `build_mcp_server`（或等价 ASGI app + fastmcp in-memory/httpx TestClient）断言 `GET /metrics` → 200、content-type 以 `text/plain` 开头且含 `version=0.0.4`、正文含 `ronin_mcp_up 1`；并加一条回归断言既有 `/mcp` 端点仍可访问/不破坏。
4. 不破坏 auth/ephemeral/七 facet 语义；不改 release 分支约定。

## 验收（冻结、可复现）
```dd-acceptance
bash -lc 'uv sync --extra dev && uv run pytest -q tests/test_metrics.py'
```