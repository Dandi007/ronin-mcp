# ronin-mcp 仓侧 /metrics 接入（ronin-mcp repo）

## 体检结论（真机实测 2026-08-29）
- `ronin-mcp.service`（systemd --user）运行中，`python -m ronin_mcp.server --config ...`，监听 127.0.0.1:5609（streamable-http）。
- `GET /metrics` → 404（无自指标）。可观测面空白。
- 技术形态：FastMCP（fastmcp>=2.0.0），`build_mcp_server()` 组合 7 个 facet 到单 FastMCP 实例；
  测试用 FastMCP 内存 Client + mock transport（tests/doubles.py）。pytest dev 依赖，tests/*.py。
- git 9 残留（.dev-dispatch，已只删不改清理）。

## 交付范围（全部落在 ronin-mcp repo）
1. `ronin_mcp/server.py`：在 `build_mcp_server` 产出的 FastMCP 实例上新增 `GET /metrics` 自定义路由
   （`@mcp.custom_route("/metrics", methods=["GET"])` 或等价），返回 `text/plain` 正文
   `ronin_mcp_up 1`（`media_type="text/plain; version=0.0.4"`）。
   要求：process-local、零依赖、不触 AuthState/各 backend/facet，数据面异常不得令 /metrics 5xx；
   进程面存活交给 Prometheus `up` 判据。不改既有工具与路由行为。
2. `tests/test_metrics.py`（新增）：用 `build_mcp_server` + FastMCP `http_app()` + httpx ASGITransport
   断言 `GET /metrics` → 200、content-type 以 text/plain 开头且含 version=0.0.4、
   正文含 `ronin_mcp_up 1`。
3. 卫生：`git status --short` 为空；本单不执行部署。

## 判据对照（goal.md §判据 1-5）
1. 指标可查：`ronin_mcp_up` 经 `127.0.0.1:5609/metrics` 暴露；
2-5. 平台侧（fleet-sentinel scrape job + 告警规则 + Grafana 面板 + drill file_sd 演练通道）
由后续 fleet-sentinel 单承接；本单只做仓侧，验收即下方命令。

```dd-acceptance
bash -lc 'V="$(mktemp -d)"; python3 -m venv "$V/venv" && "$V/venv/bin/pip" install -q -e . pytest httpx && "$V/venv/bin/python" -m pytest -q tests/test_metrics.py'
```