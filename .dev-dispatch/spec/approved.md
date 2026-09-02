# M3 返工 —— ronin-mcp 逐工具处置：退役显式化 + 全量回归可见

## 背景（监督面 2026-09-03 01:2x 拒收，逐条照抄）
前单 dev-fg-cd44b133614e 被拒收：全量 `uv run pytest -q` 由基线 106 passed 被打到 31 failed，根因是把 dev / gate / pump 三族工具从 `ronin_mcp/server.py` 的注册里摘除，但它们的测试（test_development.py 12 + test_gate.py 7 + test_pump.py 10 = 29，另 test_ephemeral / test_backend_errors 各 1）一条没动，全部撞 `Unknown tool`。方向对、做法错：退役不该「摘掉注册让调用者撞 Unknown tool」，而该「保留注册、显式返回已退役拒绝」。

## 第 0 步（铺底，前单已做过、本单重做）—— 把现役源码纳入治理
ronin-mcp 仓库 `main`（2b4ba18）仅 `README.md`，现役源码未被版本控制。现役部署源码在 `/data/apps/ronin-mcp/releases/5cf5375f9442/`（`ronin_mcp/*.py` + `tests/*.py` + `pyproject.toml` + `uv.lock` + `config/` + `deploy/`，全量 106 测试全绿基线）。请把该部署源码逐字 vendor 进仓库并提交，**显式排除 `.dev-dispatch/` 与 `.dd-evidence/` 协议子树**（不夹带上一张单的派发身份残留）。

## 第 1 步（本单核心，前单做错处）—— 退役显式化（监督面倾向的第 2 种做法）
**退役 = 保留工具在 `tools/list` 注册表（可见、可调用），调用时返回显式、结构化、闭合的「已退役」拒绝码**，不得是 `Unknown tool`、不得是 `Connection refused` / `BACKEND_UNAVAILABLE` / `No such file or directory` 这类像故障的错误。

## 交付物
1. 新建 `ronin_mcp/disposition.py` 并作为 59 工具判定 SSoT（available / fixed / retired 三分，逐条理由，一个不落）。
2. `ronin_mcp/server.py`：dev（10）/ gate（2）/ pump（3）三族 15 个工具**保持注册**，但其调用路径返回显式 `RETIRED` 拒绝（结构化拒绝码 + 退役理由，紧跟既有 backend-error 口径）；**不得**改成「从 tools/list 消失」。
3. wf/fs 族 22 个工具：修 `asyncio.run()` 不能在运行中 event loop 再调的缺陷（改为直接 await / 走既有 async 入口），保持可用，属「修」不是「退役」。
4. 阴性用例：改写 `tests/test_development.py` / `test_gate.py` / `test_pump.py`（及 `test_ephemeral.py` / `test_backend_errors.py` 中触及退役工具者）——把针对已退役工具的调用用例改写成阴性断言「调用返回 RETIRED 拒绝」；15 个退役工具各至少一条**能红的阴性用例**（把该工具改回「可用」实现，用例必须变红）。
5. **零删除既有测试**：改写非删除；净删必须换来守着退役事实的新断言。
6. **dd-acceptance 加严为全量 `uv run pytest -q`**（整仓回归，不得只盯 `tests/test_m3_roninmcp_disposition.py`）。

## 双向判据（对齐 goal.md M3 / DoD 3，不可弱）
- 阳性（DoD 3）：每一个 ronin_mcp 工具**要么可用 / 已修、要么被显式标记为退役**——不存在「工具在注册表上、调用却像故障一样挂掉」的第三种状态。
- 阴性（退役可回归）：退役必须显式、可回归——把某退役工具改回「可用」，有阴性用例变红；`RETIRED` 拒绝必须是明确「已退役」语义，不得是 Unknown tool / Connection refused。

## 验收标准（机械判定）
- 全量 `uv run pytest -q` 相对当刻基线（106 passed，vendor 之后立即跑一次全量回归作为基线）**无新增失败**（即全绿，含改写后的阴性用例与既有 106 条）。
- 15 个退役工具各有至少一条能红的阴性用例。

## 红线
- 不越界执行生产退役（生产上下线归 wf-3ffd90）；不改写/删除其它既有测试；不碰可用族（agent-bus 21 个）的现役行为；不夹带 `.dev-dispatch`/`.dd-evidence`；prod 主 checkout 只 ff-only，改动只进 worktree。

## 验收
```dd-acceptance
uv sync --frozen
uv run pytest -q
```