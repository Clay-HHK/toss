# 系统架构

## 总览

```
┌─────────────────────────────────────────────────────────┐
│  客户端                                                  │
│                                                         │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────┐  │
│  │  Python CLI  │   │  MCP Server  │   │   Skills   │  │
│  │  (toss push) │   │ (toss-mcp)   │   │ (自然语言) │  │
│  └──────┬───────┘   └──────┬───────┘   └─────┬──────┘  │
│         └──────────────────┴─────────────────┘         │
│                            │ HTTPS                      │
└────────────────────────────┼────────────────────────────┘
                             │
┌────────────────────────────┼────────────────────────────┐
│  Cloudflare 边缘节点        │                            │
│                            ▼                            │
│              ┌─────────────────────────┐                │
│              │   Cloudflare Worker     │                │
│              │   (TypeScript)          │                │
│              │                         │                │
│              │  认证 ─ CORS ─ 限流     │                │
│              │  中间件                  │                │
│              │                         │                │
│              │  /api/v1/documents  ────┼──► R2 存储     │
│              │  /api/v1/contacts   ────┼──► D1 数据库   │
│              │  /api/v1/groups     ────┼──► D1 数据库   │
│              │  /api/v1/spaces     ────┼──► R2 + D1    │
│              │  /api/v1/auth       ────┼──► GitHub API │
│              └─────────────────────────┘                │
└─────────────────────────────────────────────────────────┘
```

---

## 组件说明

### Python CLI（`src/toss/`）

| 模块 | 作用 |
|------|------|
| `cli/` | Click 命令定义（push、pull、contacts、groups、spaces、profiles） |
| `client/` | 封装 Worker API 的 HTTP 客户端 SDK（基于 httpx） |
| `config/` | 多 profile 配置文件读写、版本迁移 |
| `auth/` | GitHub PAT 和 Device Flow 认证、JWT 存储 |
| `sync/` | 共享空间的 SHA-256 清单差异计算 |
| `mcp/` | FastMCP 服务，向 Claude Code / Cursor 暴露 10 个工具 |

### Cloudflare Worker（`worker/`）

| 模块 | 作用 |
|------|------|
| `handlers/` | API 路由处理器：documents、contacts、groups、spaces、auth、cleanup |
| `middleware/` | JWT 验证、CORS 响应头、速率限制（60 次/分钟/用户） |
| `services/` | 数据库（D1）、对象存储（R2）、GitHub API 客户端 |
| `schema.sql` | D1 表结构定义 |

### 存储

| 存储 | 内容 |
|------|------|
| **R2** | 文件内容（二进制 blob，以 document_id 为 key） |
| **D1** | 用户、联系人、文档元数据、群组、空间 |
| **KV** | 会话缓存（预留，供未来使用） |

---

## 认证流程

```
用户                CLI                  Worker            GitHub
 │                   │                     │                  │
 │  toss login --pat │                     │                  │
 │──────────────────►│                     │                  │
 │                   │  POST /api/v1/auth  │                  │
 │                   │  { pat: "ghp_..." } │                  │
 │                   │────────────────────►│                  │
 │                   │                     │  GET /user       │
 │                   │                     │─────────────────►│
 │                   │                     │  { login, id }   │
 │                   │                     │◄─────────────────│
 │                   │  { jwt: "eyJ..." }  │                  │
 │                   │◄────────────────────│                  │
 │                   │                     │                  │
 │  (JWT 存入        │                     │                  │
 │  credentials.yaml)│                     │                  │
```

后续所有请求都带 `Authorization: Bearer <jwt>`，Worker 在每个请求上验证签名（密钥为 `JWT_SECRET`）。

---

## 多 Profile 配置结构

```
~/.toss/
├── config.yaml
│     current_profile: work
│     profiles:
│       work:  { server: { base_url: https://work.workers.dev } }
│       lab:   { server: { base_url: https://lab.workers.dev  } }
│     sync: { ... }
│
├── credentials.yaml   (chmod 600)
│     work: { jwt: "eyJ...", github_username: clay-hhk }
│     lab:  { jwt: "eyJ...", github_username: clay-hhk }
│
└── spaces/
      my-proj/   ← 本地空间文件
```

`ConfigManager` 根据 `current_profile` 选取当前 profile，向所有调用方返回正确的服务器地址和 JWT。旧版（v0.1）的单服务器配置在首次读取时自动迁移为 `default` profile。

---

## 文档生命周期

```
push
 └─► Worker 在 D1 存储元数据（文件名、发送方、接收方、大小、过期时间）
 └─► Worker 在 R2 存储文件内容（key: document_id）

inbox
 └─► Worker 查询 D1：recipient = 我 AND pulled = false

pull
 └─► Worker 从 R2 流式传输内容 → 客户端写入磁盘
 └─► Worker 在 D1 将文档标记为 pulled = true

cleanup（每日定时任务）
 └─► Worker 删除 D1 中 expires_at < now 的记录
 └─► Worker 删除对应的 R2 对象
```

---

## 项目目录结构

```
toss/
├── src/toss/                    # Python CLI + SDK
│   ├── cli/
│   │   ├── main.py              # init, login, whoami, logout, join, switch
│   │   ├── contacts.py          # contacts add/list/remove
│   │   ├── groups.py            # group create/list/invite/join/push
│   │   ├── profiles.py          # profile list/add/remove
│   │   ├── push_pull.py         # push, pull, inbox
│   │   └── spaces.py            # space create/list/sync
│   ├── client/
│   │   ├── base.py              # TossClient (httpx)
│   │   ├── contacts.py
│   │   ├── documents.py
│   │   ├── groups.py
│   │   └── spaces.py
│   ├── config/
│   │   ├── models.py            # Frozen dataclasses
│   │   └── manager.py           # 多 profile 配置管理 + 迁移
│   ├── auth/
│   │   ├── github.py            # PAT + Device Flow
│   │   └── token_store.py       # 按 profile 存储 JWT
│   ├── sync/
│   │   ├── state.py             # 本地清单（SHA-256）
│   │   └── engine.py            # 差异计算 + 上传/下载
│   └── mcp/
│       └── server.py            # FastMCP，10 个工具
│
├── worker/                      # Cloudflare Worker (TypeScript)
│   ├── src/
│   │   ├── index.ts
│   │   ├── router.ts
│   │   ├── handlers/
│   │   ├── middleware/
│   │   └── services/
│   └── schema.sql
│
├── npm/                         # npm 包（toss-cli 轻量 wrapper）
├── hooks/                       # Claude Code Hooks
├── skills/                      # Claude Code Skills
├── docs/                        # 英文文档
│   ├── getting-started.md
│   ├── cli-reference.md
│   ├── profiles.md
│   ├── claude-code.md
│   ├── self-hosting.md
│   └── architecture.md
├── docs/zh/                     # 中文文档
│   ├── getting-started.md
│   ├── cli-reference.md
│   ├── profiles.md
│   ├── claude-code.md
│   ├── self-hosting.md
│   └── architecture.md
├── .mcp.json
└── pyproject.toml
```
