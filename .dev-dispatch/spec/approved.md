# M3 —— ronin-mcp 处置：修，或退役（判定 + 改指）

ronin-mcp（:5609 聚合门面，59 工具）约 38/59 坏或死，而 Prometheus target up=1、systemd active、面板全绿（wf-525fd4 goal.md M3）。本线负责**判定 + 改指**；退役的**执行**归 wf-3ffd90，本单不越界执行生产退役。

## 现状（监督面 2026-09-02 15:1x 真机逐族）

- bus 族（alias/agent/chatgroup/msg/inbox ~21）：可用（上游总线活着）。
- dev/gate ~13：`BACKEND_UNAVAILABLE: controller GET /v1/developments unavailable: Connection refused`（上游 dev-dispatch controller 已退役）。
- pump 3：`No such file or directory: /data/ronin/runs/...`（指已退役泵栈）。
- wf/fs ~22：`asyncio.run() cannot be called from a running event loop`（**实现缺陷**，非过时；对应 katana 面仍活，修得好）。

## 交付物

1. 一份**逐工具判定结论**（落文档并可在测试里核对）：59 个 ronin-mcp 工具，每个要么「可用」、要么「修」、要么「退役」，一个不落。
2. **改指**：退役类工具（dev/gate、pump）从调用面撤下——要么移除、要么显式返回 `RETIRED`/`NOT_SUPPORTED` 拒绝码（不得继续 up=1 仍暴露、不得装作可用）；wf/fs 类实现缺陷修复（`asyncio.run()` 不能在运行中的 event loop 里再调——改为直接 await / 用既有 async 入口）。
3. `tests/test_m3_roninmcp_disposition.py`（本单验收目标，含独立 negative 用例）。

## 双向判据（不可弱，对齐 goal.md M3 / DoD 3）

- **阳性（DoD 3）**：每一个 ronin-mcp 工具**要么可用、要么被显式标记为退役**——不存在「看起来能用实则后端已死」的第三种状态。
- **阴性（不许恒亮 / 退役可回归）**：一个工具的退役必须显式、可回归——给它加回一个本应退役的调用 → 有用例**变红**（退役复发会被抓住）。

## 红线纪律

- 退役动作本身（生产上下线）归 wf-3ffd90；本单只做判定 + 改指（源码层把退役工具显式标记/撤下），不越界执行生产退役。
- wf/fs 22 个是修复不是删除——修 asyncio 用法，katana 面仍活。
- 判定以真机 `tools/list` 与各工具调用回显为准，逐条附证据，禁止凭空推断。
- 不删除/改写其它既有测试；新增文件过 ruff/format。

## 环境注记（本轮取证）

ronin-mcp git 仓库 `main`（2b4ba18）仅提交 README.md，`ronin_mcp/` 源码未纳入版本控制；现役部署源码在 `/data/apps/ronin-mcp/releases/5cf5375f9442/`（`ronin_mcp/*.py`、`pyproject.toml`、`tests/*.py` 齐全）。实现需**先把现役源码纳入仓库并提交**（改指前先把源纳入治理），再在源码上落地判定与改指。

## 验收

```dd-acceptance
uv sync --frozen
uv run pytest -q tests/test_m3_roninmcp_disposition.py
```