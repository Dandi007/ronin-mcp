# SPEC — Ronin MCP（浪人 MCP）

> **Spec Revision:** `specrev_ronin_mcp_001`
> **Status:** draft → ready for H0
> **Date:** 2026-08-19
> **Work Folder:** wf-4b78b0
> **Prior Art:** `/data/code/self/agent-bus/agent_bus/mcp_gateway.py` (agent-bus MCP gateway, read 2026-08-19)

---

## 北极星

把浪人（ronin = goal-agent 自主开发舰队）的**全部控制面**，用「一个 MCP」等效暴露给任何 agent（含用户）。核心示范面 = 好友/群组/消息的增删改查，但不限于此——dd 派单 / work-folder / 泵状态 / gate 审批都能经它操作。

**「浪人 MCP」= 浪人舰队的管理台，把散落在 agent-bus / dev-dispatch / goal-agent / work-folder / agent-runtime 的控制面收拢到一个 `ronin_*` MCP 命名空间下。**

---

## 实现形态：聚合 façade（aggregating façade）

### 选择

**聚合 façade**：一个 MCP server，内部向多个后端（agent-bus HTTP、loop-engine Controller HTTP、katana-work-folder MCP、文件系统 `/data/ronin/runs/`）发起 HTTP 调用，在入口层统一命名、统一授权、统一错误包装。

### 理由

| 维度 | 透传 façade | 聚合 façade | 纯命名整理 |
|------|------------|------------|-----------|
| 命名统一 | 需改后端 | **入口统一** | 仅改名 |
| 授权护栏 | 分散在各后端 | **入口集中** | 无 |
| 运维复杂度 | 多 MCP 端口 | **单 MCP 端口** | 多 MCP 端口 |
| 实现成本 | 低 | 中 | 最低 |
| 写面护栏 | 依赖后端各自实现 | **统一注入** | 无 |

- **选聚合 façade 的核心理由**：写面护栏必须在入口统一执行，不能依赖三个后端各自的授权模型。`gd:` 前缀检查、ephemeral 模式、生产写显式授权——这些规则在一个 MCP 入口落地，比分散在三个后端各自实现更可审计、更不容易出现旁路。
- **不选纯透传**：透传意味着每个后端暴露自己的 MCP，agent 需要知道三个 MCP 的端口和命名空间，且授权逻辑分散。
- **不选纯命名整理**：只是改名不做聚合，授权护栏无处安放。

### 后端依赖

| 后端 | 协议 | 地址 | 用途 |
|------|------|------|------|
| agent-bus HTTP | HTTP REST | `http://127.0.0.1:7490` | alias / agent / channel / message / consume / ack |
| loop-engine Controller | HTTP REST | `http://127.0.0.1:7460` | development CRUD / gate / steer / control |
| katana-work-folder MCP | MCP (streamable-http) | 通过 MCP client 调用 | work folder / file ops |
| 文件系统 | 本地读 | `/data/ronin/runs/` | pump run 状态 |

---

## 技术栈

**Python ≥3.11 + FastMCP ≥2 + httpx + pyyaml + pydantic ≥2**

选择理由：
1. **与 agent-bus 一致**：同一语言、同一 MCP 框架、同一 HTTP 客户端。agent-bus 的 `mcp_gateway.py` 是直接参考实现，代码骨架（FastMCP 初始化、`_bus_get/_bus_post` 错误包装、`@mcp.tool()` 装饰器、`main()` 启动）可照抄。
2. **部署同构**：systemd unit + `EnvironmentFile=` + `streamable-http` 传输，与 agent-bus MCP (:5608) 和 loop-engine MCP (:5606) 完全一致。
3. **运维面最小**：运维只需管一个 Python 包（`uv sync`），不需要多语言 runtime。

---

## 目录结构

```
/data/code/self/ronin-mcp/
├── pyproject.toml                  # hatchling; py>=3.11; fastmcp>=2, httpx, pyyaml, pydantic>=2
├── README.md                       # 概念、信任边界、curl quickstart、跨语言启动示意
├── spec.md                         # 本文件（冻结契约）
├── ronin_mcp/
│   ├── __init__.py
│   ├── config.py                   # load_config, 凭证注入（从 /data/ronin/secrets/ 读 token 文件）
│   ├── server.py                   # build_mcp_server + main()
│   ├── auth.py                     # 授权护栏：gd: 前缀 / ephemeral / 生产写显式授权
│   ├── backends/
│   │   ├── __init__.py
│   │   ├── agent_bus.py            # agent-bus HTTP client（仿 mcp_gateway.py _bus_get/_bus_post）
│   │   ├── dev_dispatch.py         # loop-engine Controller HTTP client
│   │   ├── work_folder.py          # katana-work-folder MCP client
│   │   └── pump_state.py          # 读 /data/ronin/runs/ 文件系统
│   └── facets/
│       ├── __init__.py
│       ├── alias.py                # ronin_alias_* / ronin_agent_*
│       ├── chatgroup.py            # ronin_chatgroup_*
│       ├── messaging.py            # ronin_msg_* / ronin_inbox_*
│       ├── development.py          # ronin_dev_*
│       ├── work_folder.py          # ronin_wf_* / ronin_fs_*
│       ├── pump.py                 # ronin_pump_*
│       └── gate.py                 # ronin_gate_*
├── tests/
│   ├── conftest.py                 # fixtures: ephemeral bus + tmp dir
│   ├── test_auth.py                # 写面护栏：gd: 通过 / 生产写被拒
│   ├── test_alias.py
│   ├── test_chatgroup.py
│   ├── test_messaging.py
│   ├── test_development.py
│   ├── test_work_folder.py
│   ├── test_pump.py
│   └── test_gate.py
├── config/
│   └── config.yaml.example
└── deploy/
    └── ronin-mcp.service           # systemd user unit
```

---

## 设计判据（必答）

### 判据 1：读写分离与授权

**原则**：读面自由，写面必须有护栏。

**读面工具**（以下工具不做授权检查，任意已认证 agent 可调）：
- 所有 `*_list`、`*_get`、`*_resolve`、`*_events`、`*_evidence`、`*_whoami`、`*_search`、`*_stat`、`*_capabilities`、`*_read`、`*_read_bytes`

**写面工具**（以下工具在入口做授权检查）：
- 所有 `*_register`、`*_create`、`*_rebind`、`*_send`、`*_broadcast`、`*_approve`、`*_reject`、`*_start`、`*_steer`、`*_control`、`*_reconfigure`、`*_relock`、`*_add_member`、`*_remove_member`、`*_save`、`*_write`、`*_edit`、`*_delete`、`*_copy`、`*_rename`、`*_batch`、`*_evidence_put`、`*_evidence_migrate`、`*_append_progress`、`*_reconcile`、`*_reindex`、`*_consume`（不含 ack/nack/renew，consume 是消费语义含副作用）

**护栏规则**（按优先级）：

1. **Ephemeral 模式**（`--ephemeral` 启动或 `RONIN_EPHEMERAL=1`）：
   - 所有写操作路由到 `--ephemeral` 的 agent-bus 实例（agent-bus 自身支持 `--ephemeral`）
   - 所有 dd 写操作走 `--ephemeral` 的 Controller 实例
   - 所有 work-folder 写操作走临时目录
   - **无任何限制**，全写面开放

2. **`gd:` 前缀**（非 ephemeral 模式）：
   - 测试/开发身份：alias 以 `gd:` 开头、agent_id 以 `gd:` 开头、channel_id 以 `gd:` 开头、work_folder 以 `gd:` 开头
   - 面向 `gd:` 资源的写操作**直接放行**
   - 这允许开发过程中自由创建测试 alias / 群组 / work-folder 而不污染生产命名空间

3. **生产写**（非 `gd:` 前缀，非 ephemeral）：
   - 必须显式授权：`RONIN_PROD_WRITE=1` 环境变量或 `--prod-write` 启动参数
   - 未授权时返回明确错误：`{"code": "PROD_WRITE_NOT_AUTHORIZED", "message": "Production write requires RONIN_PROD_WRITE=1 or --prod-write. Use gd: prefix for test resources."}`
   - **不得静默 mutate 生产数据**

4. **Gate 特殊规则**：
   - `ronin_gate_approve` / `ronin_gate_reject` 始终要求 `RONIN_PROD_WRITE=1`（即使 target 是 `gd:` development），因为 gate 审批是 B-class 不可逆操作
   - `ronin_dev_create` 面向生产 repo 时要求 `RONIN_PROD_WRITE=1`

**实现位置**：`ronin_mcp/auth.py` 的 `check_write_auth(target: str, prod_write_required: bool)` 函数，在每个写面 tool 入口调用。

### 判据 2：Token 红线

**凭证永不进 argv / git / 日志 / model context。**

| 凭证 | 存储位置 | 权限 | 注入方式 |
|------|---------|------|---------|
| `BUS_GATEWAY_TOKEN` | `/data/ronin/secrets/ronin-mcp.token` | 0600 | 文件读取，`config.py` 启动时 `open().read().strip()` |
| `BUS_ADMIN_TOKEN` | `~/.config/agent-bus/secrets.env` | 0600 | 系统已有，不复制 |
| Dev MCP 凭证 | 无需（loop-engine Controller 127.0.0.1 无鉴权） | — | — |
| Work-folder 凭证 | 由 katana-work-folder MCP 管理，ronin-mcp 通过 MCP client 调用 | — | — |

**具体措施**：
- `ronin_mcp/config.py` 从文件读 token，读后立即关文件，不进入任何日志
- `@mcp.tool()` 的参数**永不包含 token 字段**——仿 agent-bus 的 `as_agent_id` 委托模式
- Tool 返回值中**永不包含 token 明文**——仿 agent-bus `bus_agent_register` 的 `del result["token"]` 做法
- 启动日志不打印任何 credential 相关环境变量
- systemd unit 的 `EnvironmentFile=` 指向 0600 文件，systemd 自身保证不泄露到 `/proc`

### 判据 3：无头拉起

**MCP 必须能被 agent-runtime 无头启动，注入舰队座位。**

- **传输**：`streamable-http`（FastMCP 默认），绑定 `127.0.0.1:<port>`
- **端口**：建议 `5609`（5601–5608 已被占用，5609 空闲）
- **systemd unit**：`~/.config/systemd/user/ronin-mcp.service`
  ```
  [Service]
  Type=simple
  ExecStart=/data/code/self/ronin-mcp/.venv/bin/python -m ronin_mcp.server
  EnvironmentFile=%h/.config/ronin/secrets.env
  Restart=on-failure
  RestartSec=5
  ```
- **agent-runtime 注册**：在 `profiles/agents.yaml` 添加座位，`mcpServers.ronin-mcp` 指向 `http://127.0.0.1:5609/mcp`
- **Ephemeral 模式**：`--ephemeral` 参数启动临时 agent-bus 实例 + 临时 Controller 实例，所有状态在进程退出时清理
- **启动顺序**：`After=agent-bus-server.service agent-bus-mcp.service loop-engine-development-mcp.service`

---

## Tool 清单（全部 7 面）

### 面 1：好友（Alias 注册表）

| Tool | 类型 | 描述 | 后端 |
|------|------|------|------|
| `ronin_alias_list(kind?, as_agent_id?)` | 读 | 列出所有 alias | agent-bus `GET /v1/aliases` |
| `ronin_alias_resolve(alias, as_agent_id?)` | 读 | 解析 alias → agent_id | agent-bus `GET /v1/aliases/{alias}` |
| `ronin_alias_register(alias, kind, agent_id, as_agent_id?)` | 写 | 注册 alias（须 `gd:` 或 `RONIN_PROD_WRITE=1`） | agent-bus `POST /v1/aliases` |
| `ronin_alias_rebind(alias, agent_id, expected_current_agent_id, as_agent_id?)` | 写 | 换绑 alias（CAS） | agent-bus `POST /v1/aliases/{alias}/rebind` |
| `ronin_agent_list(kind?, as_agent_id?)` | 读 | 列出 agent | agent-bus `GET /v1/agents` |
| `ronin_agent_whoami(as_agent_id?)` | 读 | 当前身份 | agent-bus `GET /v1/agents/whoami` |
| `ronin_agent_register(agent_id, display_name, kind?, as_agent_id?)` | 写 | 注册 agent（须 `gd:` 或 `RONIN_PROD_WRITE=1`） | agent-bus `POST /v1/agents` |

### 面 2：群组（Chatgroup）

> **注意**：agent-bus 当前未实现 chatgroup 专用表/API。chatgroup 本阶段用 fanout channel + 命名约定实现：`chatgroup:<name>` 前缀 channel，`delivery_mode='fanout'`，`visibility='public'`（组内可见）。成员管理通过 channel 的 subscribe/unsubscribe 实现。后续 agent-bus 若新增 chatgroup 原生支持，本面改为透传。

| Tool | 类型 | 描述 | 后端 |
|------|------|------|------|
| `ronin_chatgroup_create(channel_id, display_name?, members?, as_agent_id?)` | 写 | 建群（须 `gd:` 或 `RONIN_PROD_WRITE=1`） | agent-bus `POST /v1/channels` + 批量 subscribe |
| `ronin_chatgroup_list(prefix?, as_agent_id?)` | 读 | 列群（filter `chatgroup:` 前缀 channel） | agent-bus `GET /v1/channels?prefix=chatgroup:` |
| `ronin_chatgroup_get(channel_id, as_agent_id?)` | 读 | 群详情（含成员列表） | agent-bus `GET /v1/channels` + `/v1/deliveries` |
| `ronin_chatgroup_add_member(channel_id, agent_id, as_agent_id?)` | 写 | 加人（须 `gd:` 或 `RONIN_PROD_WRITE=1`） | agent-bus `POST /v1/channels/{id}/subscribe` |
| `ronin_chatgroup_remove_member(channel_id, agent_id, as_agent_id?)` | 写 | 踢人（须 `gd:` 或 `RONIN_PROD_WRITE=1`） | agent-bus `DELETE /v1/channels/{id}/subscribe` |
| `ronin_chatgroup_send(channel_id, payload, idempotency_key, as_agent_id?)` | 写 | 群发消息（须 `gd:` 或 `RONIN_PROD_WRITE=1`） | agent-bus `POST /v1/channels/{id}/publish` |

### 面 3：消息（单发 / 群发 / 收件箱）

| Tool | 类型 | 描述 | 后端 |
|------|------|------|------|
| `ronin_msg_send(alias, payload, idempotency_key, from_alias?, as_agent_id?)` | 写 | 向 alias 发 `agent.msg.v1`（须 `gd:` 或 `RONIN_PROD_WRITE=1`） | agent-bus `POST /v1/channels/agent:{alias}/publish` |
| `ronin_msg_broadcast(payload, idempotency_key, as_agent_id?)` | 写 | 向在线 human principal 广播（须 `RONIN_PROD_WRITE=1`） | agent-bus `POST /v1/broadcast` |
| `ronin_inbox_consume(alias?, max_messages?, lease_ms?, as_agent_id?)` | 写 | 消费自己（或指定 alias）的收件箱 | agent-bus `POST /v1/channels/agent:{alias}/consume` |
| `ronin_inbox_ack(delivery_id, lease_token, result?, as_agent_id?)` | 写 | 确认消息已处理 | agent-bus `POST /v1/deliveries/{did}/ack` |
| `ronin_inbox_nack(delivery_id, lease_token, reason?, retry_in_ms?, as_agent_id?)` | 写 | 拒绝消息（可重试） | agent-bus `POST /v1/deliveries/{did}/nack` |
| `ronin_inbox_renew(delivery_id, lease_token, lease_ms?, as_agent_id?)` | 写 | 续租约 | agent-bus `POST /v1/deliveries/{did}/renew` |
| `ronin_msg_read(channel_id, after_seq?, kind?, limit?, as_agent_id?)` | 读 | 读 channel 消息历史 | agent-bus `GET /v1/channels/{id}/messages` |
| `ronin_msg_events(after?, channel_id?, limit?, as_agent_id?)` | 读 | 读 bus 事件流 | agent-bus `GET /v1/events` |

### 面 4：dd 派单（Development 全生命周期）

| Tool | 类型 | 描述 | 后端 |
|------|------|------|------|
| `ronin_dev_list(state?, repo?, limit?, cursor?)` | 读 | 列出 development | Controller `GET /v1/developments` |
| `ronin_dev_get(development_id)` | 读 | 取 development 全状态 | Controller `GET /v1/developments/{id}` |
| `ronin_dev_events(development_id, after?, limit?)` | 读 | 取 development 事件（增量轮询） | Controller `GET /v1/developments/{id}/events` |
| `ronin_dev_evidence(development_id)` | 读 | 导出 receipt/evidence 链 | Controller `GET /v1/developments/{id}/evidence` |
| `ronin_dev_create(name, goal, idempotency_key, reason, initial_handoff, ...)` | 写 | 创建 development（须 `gd:` 或 `RONIN_PROD_WRITE=1`） | Controller `POST /v1/developments` |
| `ronin_dev_start(development_id, idempotency_key, expected_revision, reason?)` | 写 | 启动 BOOTSTRAPPING 的 development | Controller `POST /v1/developments/{id}/commands/start` |
| `ronin_dev_steer(development_id, instruction, idempotency_key, expected_revision, ...)` | 写 | 注入指令 | Controller `POST /v1/developments/{id}/commands/steer` |
| `ronin_dev_reconfigure(development_id, idempotency_key, expected_revision, ...)` | 写 | 重配置 profile/policy/commands | Controller `POST /v1/developments/{id}/commands/reconfigure` |
| `ronin_dev_control(development_id, action, idempotency_key, expected_revision, ...)` | 写 | 暂停/恢复/取消 | Controller `POST /v1/developments/{id}/commands/control` |
| `ronin_dev_relock(development_id, plugin_commit, idempotency_key, expected_revision, ...)` | 写 | 换锁 plugin commit | Controller `POST /v1/developments/{id}/commands/relock` |

### 面 5：Work Folder（读写存档）

| Tool | 类型 | 描述 | 后端 |
|------|------|------|------|
| `ronin_wf_list(limit?)` | 读 | 列出 active folders | katana-work-folder MCP `wf_list` |
| `ronin_wf_create(topic, idempotency_key?)` | 写 | 创建 folder（须 `gd:` 或 `RONIN_PROD_WRITE=1`） | katana-work-folder MCP `wf_create` |
| `ronin_wf_resume(folder_id, idempotency_key?)` | 读 | 恢复工作状态 | katana-work-folder MCP `wf_resume` |
| `ronin_wf_save(folder_id, summary?, ...)` | 写 | 保存 checkpoint | katana-work-folder MCP `wf_save` |
| `ronin_wf_search(query, top_k?)` | 读 | 搜索 folder | katana-work-folder MCP `wf_search` |
| `ronin_wf_evidence_put(folder_id, filename, content, conclusion?, idempotency_key?)` | 写 | 写入证据 | katana-work-folder MCP `wf_evidence_put` |
| `ronin_wf_evidence_migrate(folder_id, dry_run?, idempotency_key?)` | 写 | 迁移证据 | katana-work-folder MCP `wf_evidence_migrate` |
| `ronin_wf_append_progress(folder_id, entry, source_session_id, idempotency_key)` | 写 | 追加进展 | katana-work-folder MCP `wf_append_progress` |
| `ronin_wf_reconcile(scope_prefixes?, control_paths?, idempotency_key?)` | 写 | 安全恢复清单 | katana-work-folder MCP `wf_reconcile` |
| `ronin_wf_reindex(dry_run?, idempotency_key?)` | 写 | 重建 INDEX | katana-work-folder MCP `wf_reindex` |
| `ronin_fs_list(folder_id, dirname?)` | 读 | 列目录 | katana-work-folder MCP `fs_list` |
| `ronin_fs_read(folder_id, filename, limit?, offset?)` | 读 | 读文件 | katana-work-folder MCP `fs_read` |
| `ronin_fs_read_bytes(folder_id, filename, limit?, offset?)` | 读 | 读二进制 | katana-work-folder MCP `fs_read_bytes` |
| `ronin_fs_stat(folder_id, filename)` | 读 | 文件状态 | katana-work-folder MCP `fs_stat` |
| `ronin_fs_resolve(folder_id, filename?)` | 读 | 解析 brief | katana-work-folder MCP `fs_resolve` |
| `ronin_fs_create(folder_id, filename, content, idempotency_key?)` | 写 | 创建文件 | katana-work-folder MCP `fs_create` |
| `ronin_fs_write(folder_id, filename, content, idempotency_key?)` | 写 | 写文件 | katana-work-folder MCP `fs_write` |
| `ronin_fs_edit(folder_id, filename, old_string, new_string, replace_all?, idempotency_key?)` | 写 | 编辑文件 | katana-work-folder MCP `fs_edit` |
| `ronin_fs_delete(folder_id, filename, idempotency_key?)` | 写 | 删文件 | katana-work-folder MCP `fs_delete` |
| `ronin_fs_copy(source_folder_id, source_filename, dest_folder_id, dest_filename, idempotency_key?)` | 写 | 复制文件 | katana-work-folder MCP `fs_copy` |
| `ronin_fs_rename(source_folder_id, source_filename, dest_folder_id, dest_filename, idempotency_key?)` | 写 | 重命名 | katana-work-folder MCP `fs_rename` |
| `ronin_fs_batch(folder_id, operations, idempotency_key?)` | 写 | 批量操作 | katana-work-folder MCP `fs_batch` |
| `ronin_fs_capabilities()` | 读 | 列出能力 | katana-work-folder MCP `fs_capabilities` |

### 面 6：泵状态（Goal-Agent Pump）

| Tool | 类型 | 描述 | 后端 |
|------|------|------|------|
| `ronin_pump_list(limit?, status?)` | 读 | 列出 pump runs | 文件系统 `/data/ronin/runs/` |
| `ronin_pump_get(run_id)` | 读 | 取 run 状态（run.json + terminal.json） | 文件系统 `/data/ronin/runs/{run_id}/` |
| `ronin_pump_rounds(run_id, after_round?, limit?)` | 读 | 取 pump 轮次事件（rounds.jsonl） | 文件系统 `/data/ronin/runs/{run_id}/rounds.jsonl` |

**实现细节**：
- `ronin_pump_list`：`ls -t /data/ronin/runs/`，读每个 `run.json` 的 `run_id`/`folder_id`/`status`/`started_at`/`terminal_at`/`rounds`/`route_attempts`
- `ronin_pump_get`：返回 `run.json` + `terminal.json`（若存在）的合并内容
- `ronin_pump_rounds`：读 `rounds.jsonl`（JSONL 格式），支持 `after_round` 增量拉取
- 全部只读，文件系统操作不需要写权限

### 面 7：Gate 审批

| Tool | 类型 | 描述 | 后端 |
|------|------|------|------|
| `ronin_gate_approve(development_id, gate_id, idempotency_key, expected_revision, operator_identity, reason?)` | 写 | 批准 gate（始终要求 `RONIN_PROD_WRITE=1`） | Controller `POST /v1/developments/{id}/commands/gate` |
| `ronin_gate_reject(development_id, gate_id, idempotency_key, expected_revision, operator_identity, reason?)` | 写 | 拒绝 gate（始终要求 `RONIN_PROD_WRITE=1`） | Controller `POST /v1/developments/{id}/commands/gate` |

**Gate 特殊规则**：gate 审批是 B-class 不可逆操作。即使 `gd:` 前缀的 development，gate 审批也始终要求 `RONIN_PROD_WRITE=1`。这防止测试流程中意外审批真实 gate。

---

## 委托模型

仿 agent-bus 的【受限委托】模式：

```
Agent → ronin-mcp (tool call, as_agent_id="alice")
         │
         ├─→ agent-bus HTTP (Authorization: Bearer <ronin-mcp-gateway-token>
         │                    X-Bus-On-Behalf-Of: alice)
         │
         ├─→ loop-engine Controller HTTP (X-Operator-Identity: alice)
         │
         └─→ katana-work-folder MCP (MCP client, as ronin-mcp)
```

- **ronin-mcp 自身**注册为 agent `ronin-mcp`（`kind='service'`，`can_delegate=1`，`is_admin=0`）
- **Tool 参数收 `as_agent_id`，永不收 token**——凭证从 `/data/ronin/secrets/` 文件注入，不进 model context
- **信任边界**：能触达 ronin-mcp 的东西可以扮作任意 agent（同 agent-bus 的诚实交代）。这仅可接受因为 MCP 绑 `127.0.0.1` 且模型本就有同机文件读权

---

## 配置

### `config.yaml`

```yaml
server:
  host: "127.0.0.1"
  port: 5609

backends:
  agent_bus:
    url: "http://127.0.0.1:7490"
    gateway_token_file: "/data/ronin/secrets/ronin-mcp.token"
  dev_dispatch:
    url: "http://127.0.0.1:7460"
  work_folder:
    # MCP client 连接 katana-work-folder MCP
    mcp_url: "http://127.0.0.1:5605/mcp"  # 待确认实际端口
  pump_state:
    runs_root: "/data/ronin/runs"

auth:
  prod_write_enabled: false  # 默认 false，须显式 --prod-write 或 RONIN_PROD_WRITE=1
  ephemeral: false           # --ephemeral 启动时设 true
```

### 凭证注入

```python
# ronin_mcp/config.py
def load_gateway_token(path: str) -> str:
    """Read token from file. Never logs, never enters argv."""
    with open(path, "r", encoding="utf-8") as f:
        token = f.read().strip()
    if len(token) < 32:
        raise ValueError(f"Gateway token in {path} too short (min 32 chars)")
    return token
```

---

## 错误模型

统一错误格式（仿 agent-bus）：

```json
{
  "code": "ERROR_CODE",
  "message": "Human-readable description",
  "details": {"retryable": false}
}
```

**ronin-mcp 特有错误码**：

| Code | HTTP | 含义 |
|------|------|------|
| `PROD_WRITE_NOT_AUTHORIZED` | 403 | 生产写未授权（须 `RONIN_PROD_WRITE=1`） |
| `GATE_REQUIRES_PROD_WRITE` | 403 | gate 审批始终要求生产写授权 |
| `BACKEND_UNAVAILABLE` | 502 | 后端不可达 |
| `BACKEND_ERROR` | 502 | 后端返回错误 |
| `INVALID_GD_PREFIX` | 400 | 要求 `gd:` 前缀但未提供 |

---

## 冒烟闭环（验收标准）

全部经 ronin-mcp（非直接 curl 后端）：

1. `ronin_agent_register("gd:test-bot", "Test Bot")` → 200
2. `ronin_agent_list()` → 列表含 `gd:test-bot`
3. `ronin_alias_register("gd:test-alias", "named", "gd:test-bot")` → 200
4. `ronin_alias_resolve("gd:test-alias")` → 返回 `gd:test-bot`
5. `ronin_msg_send("gd:test-alias", {"body": "hello"}, "ik-001")` → 200
6. `ronin_inbox_consume(alias="gd:test-alias")` → 收到消息
7. `ronin_chatgroup_create("gd:test-group", "Test Group")` → 200
8. `ronin_chatgroup_add_member("gd:test-group", "gd:test-bot")` → 200
9. `ronin_chatgroup_send("gd:test-group", {"body": "hi group"}, "ik-002")` → 200
10. `ronin_dev_list()` → 返回真实 development 列表
11. `ronin_dev_get("<real-dev-id>")` → 返回完整状态
12. `ronin_pump_list(limit=5)` → 返回近期 pump runs
13. `ronin_pump_get("<real-run-id>")` → 返回 run 状态含 `route_attempts`

**写面护栏实测**：
14. 未设 `RONIN_PROD_WRITE=1` 时 `ronin_alias_register("production-alias", ...)` → 403 `PROD_WRITE_NOT_AUTHORIZED`
15. 未设 `RONIN_PROD_WRITE=1` 时 `ronin_gate_approve(...)` → 403 `GATE_REQUIRES_PROD_WRITE`

---

## 不在范围

- **不实现 agent-bus 的 chatgroup 原生表**——本期用 fanout channel + 命名约定，chatgroup 原生支持是 agent-bus P1 的事
- **不改造 agent-bus / loop-engine / katana-work-folder 源码**——ronin-mcp 是纯聚合层，不侵入后端
- **不实现 pump 的启停控制**——只读 pump 状态，不控制泵生命周期
- **不实现 agent 协调 / 调度**——这是 consumer 的事
- **不实现 WebUI / 前端**

---

## References

- agent-bus MCP gateway（prior art）：`/data/code/self/agent-bus/agent_bus/mcp_gateway.py`
- agent-bus SSoT spec：`/data/code/self/agent-bus/docs/specs/SPEC-agent-bus.md`
- loop-engine MCP gateway：`/data/code/self/loop-engine-development-mcp/loop_engine_development_mcp/mcp_gateway.py`
- 本线 goal：`wf-4b78b0/goal.md`
- 浪人舰队谱系：`wf-103df4`
- 好友/群组/消息正编：`wf-b442dc`
- 舰队自我进化先例：`wf-23add3`
- 无头 runtime 隔离：`m-4edd06`