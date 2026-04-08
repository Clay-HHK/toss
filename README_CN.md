# Toss

[English](README.md) | [中文](README_CN.md)

**Toss** 是一个命令行工具，用于 AI agent 工具用户（Claude Code、Codex、Cursor 等）之间共享文档。不用再手动通过聊天软件传文件，一条命令搞定。

```
# 发送文件给协作者
toss push report.md xiaoming -m "帮忙看看"

# 或者用交互模式，直接输入 toss push
toss push
# → 选择文件 → 选择收件人 → 添加留言 → 完成！

# 对方一条命令拉取
toss pull
```

## 为什么需要 Toss？

AI agent 工具（Claude Code、Codex 等）会产生大量文档（分析报告、代码文件、配置文件），你经常需要分享给协作者。目前的工作流很痛苦：

1. 从 agent 工具中导出文件
2. 通过微信 / Slack / 邮件发送
3. 对方下载文件
4. 拖到自己 agent 工具的工作目录
5. 每一轮反馈都要重复上述步骤

**Toss 把这个流程简化为终端里的一条命令。** 不用切换窗口，不用拖文件，不用在聊天软件里翻找。

## 功能特性

- **推送 / 拉取**：向任何人发送文件，从收件箱拉取文件
- **交互模式**：文件选择器、联系人选择器，不用记参数
- **联系人**：给常用协作者设置别名（用 `xiaoming` 代替 `@zhangsan123`）
- **收件箱**：查看待接收文件，不下载
- **群组**：创建群组，通过邀请码邀请成员，一次推送文件给所有人
- **多团队切换**：同时加入多个团队，`toss switch <name>` 一键切换
- **零配置加入**：`toss join server/CODE` 一条命令自动配置一切
- **共享空间**：多人读写同一个文档集合，基于 SHA-256 差异同步
- **MCP Server**：Claude Code / Cursor 原生调用 Toss（10 个工具）
- **Claude Code Hooks**：启动时检查收件箱，保存文件时自动同步
- **Claude Code Skills**：自然语言封装，说"把 report.md 发给 xiaoming"即可，无需记 CLI 参数
- **速率限制**：每用户 60 次请求/分钟
- **自动清理**：过期文档 30 天后自动清理

## 架构

```
CLI (Python)  ──HTTPS──>  Cloudflare Worker (TypeScript)
                              ├── D1 (SQLite 数据库: 用户, 联系人, 文档)
                              ├── R2 (对象存储: 文件内容)
                              └── KV (缓存: 会话)
```

- **后端**：Cloudflare Workers（免费额度：10 万请求/天）
- **存储**：R2（免费额度：10GB）存文档，D1（免费额度：5GB）存元数据
- **身份认证**：GitHub 身份 + JWT 令牌

## 快速开始

> **注意**：Toss 需要后端服务。每个团队/小组需要自己部署一个 Cloudflare Worker（免费）。
> 参见下方 [自部署](#自部署) 章节，5 分钟即可完成。

### 加入团队（最简单的方式）

如果已有人部署了 Toss 服务并给了你邀请码：

```bash
# 方式 A：通过 npm（不需要 Python）
npx toss-cli join toss-api.example.workers.dev/ABCD-1234

# 方式 B：通过 uv
uvx --from git+https://github.com/Clay-HHK/toss.git toss join toss-api.example.workers.dev/ABCD-1234
```

一条命令自动配置服务器地址、提示登录、加入群组。

### 安装 CLI

```bash
# 方式 A：npm（自动安装 uv）
npm install -g toss-cli
toss --version

# 方式 B：uv（Python 用户）
uv tool install git+https://github.com/Clay-HHK/toss.git
toss --version

# 方式 C：从源码安装
git clone https://github.com/Clay-HHK/toss.git
cd toss && uv tool install .
```

### 前置条件

- GitHub 账号
- GitHub Personal Access Token（[点此创建](https://github.com/settings/tokens)，勾选 `read:user` 权限）

### 手动配置（不使用邀请码时）

```bash
# 初始化配置
toss init

# 设置你团队的服务器地址
# 编辑 ~/.toss/config.yaml，将 base_url 改为你的 Worker URL

# 使用 GitHub PAT 登录
toss login --pat

# 验证身份
toss whoami
```

### 网络说明（中国大陆）

如果你在中国大陆，`workers.dev` 域名可能需要代理。运行 toss 命令前设置代理：

```bash
export https_proxy=http://127.0.0.1:7890
```

或者添加到 shell 配置文件（`~/.zshrc`）中。

## 使用方法

### 登录

```bash
# 使用 GitHub Personal Access Token 登录
toss login --pat

# 查看当前身份
toss whoami

# 退出登录
toss logout
```

### 联系人

为协作者设置别名。对方必须已经运行过 `toss login`。

```bash
# 添加联系人并设置别名
toss contacts add zhangsan --alias xiaoming

# 查看所有联系人
toss contacts list

# 删除联系人
toss contacts remove xiaoming
```

### 推送文件

向协作者发送一个或多个文件。

```bash
# 交互模式（推荐新手使用）
toss push
# → 显示文件选择器（空格选择，回车确认）
# → 显示联系人列表或手动输入
# → 可选留言
# → 发送完成！

# 直接模式 - 推送单个文件（使用别名）
toss push report.md xiaoming

# 附带留言
toss push report.md xiaoming -m "看一下第三节"

# 推送多个文件
toss push data.csv analysis.md xiaoming

# 用 GitHub 用户名推送（不需要别名）
toss push report.md @zhangsan
```

### 查看收件箱

查看有哪些文件在等你接收。

```bash
toss inbox
```

输出示例：
```
                    Inbox (2 pending)
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ File         ┃ From        ┃ Size ┃ Message         ┃ Time             ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ report.md    │ @zhangsan   │ 2.1KB│ 帮忙看看        │ 2026-04-06 10:30 │
│ data.csv     │ @lisi       │ 15KB │                 │ 2026-04-06 09:15 │
└──────────────┴─────────────┴──────┴─────────────────┴──────────────────┘
```

### 拉取文件

从收件箱下载文件。

```bash
# 拉取全部到当前目录
toss pull

# 拉取到指定目录
toss pull --to ~/Downloads/toss

# 交互模式 - 选择要拉取的文件
toss pull --pick
# → 显示文件列表（文件名、大小、发送者）
# → 空格选择，回车确认
# → 选择保存位置
# → 下载完成！
```

### 共享空间

为团队创建一个共享文档集合。

```bash
# 创建空间
toss space create my-project --slug my-proj

# 添加团队成员
toss space add-member my-proj zhangsan

# 同步文件（在你的项目目录下）
toss space sync my-proj --dir .

# 设置默认空间（之后可以省略 slug）
toss space set-default my-proj
toss space sync

# 查看你的空间
toss space list
```

同步引擎会在本地计算 SHA-256 哈希，发送清单到服务端，只传输有变化的文件。冲突文件会保存为 `filename.server.ext`，需要手动解决。

### 群组

创建群组，方便多人共享文件。

```bash
# 创建群组
toss group create paper-team

# 分享邀请码（包含服务器地址，接收方零配置）
# 输出: Invite code: toss-api.example.workers.dev/ABCD-1234

# 其他人一条命令加入
toss join toss-api.example.workers.dev/ABCD-1234

# 向群组所有成员推送文件
toss group push report.md paper-team -m "帮忙看看"

# 查看群组列表
toss group list

# 查看群组成员
toss group members paper-team
```

### MCP Server（Claude Code / Cursor）

Toss 内置了 MCP 服务，让 Claude Code 和 Cursor 可以原生调用 Toss 工具。

如果 `toss` 已全局安装（`npm install -g toss-cli` 或 `uv tool install .`），复制 `.mcp.json` 到你的项目：

```json
{
  "mcpServers": {
    "toss": {
      "command": "toss-mcp"
    }
  }
}
```

可用的 MCP 工具：`push_document`、`pull_documents`、`list_inbox`、`list_contacts`、`add_contact`、`remove_contact`、`push_to_group`、`list_groups`、`create_group`、`join_group`。

### Claude Code Hooks

启动时自动检查收件箱，保存文件时自动同步空间。

```bash
# 安装 hooks 到 Claude Code 设置
toss init --install-hooks
```

这会向 `~/.claude/settings.json` 添加两个 hook：
- **SessionStart**：检查 Toss 收件箱，显示待接收数量
- **PostToolUse (Write/Edit)**：写入空间目录中的文件时自动同步

### Claude Code Skills

`skills/` 目录下包含两个 Claude Code skill，让你在 Claude Code 里用自然语言操作 Toss，无需记忆命令参数。

**安装**（复制到你的 Claude Code skills 目录）：

```bash
cp -r skills/toss-push skills/toss-pull ~/.claude/skills/
```

**toss-push** — 触发短语示例：
- "把 report.md 发给 xiaoming"
- "push data.csv 和 notes.md 给 @zhangsan，附言：帮忙看看"

**toss-pull** — 触发短语示例：
- "拉取我的收件箱" / "下载 toss 里的文件"
- "有人给我发东西了吗？"（只列出，不下载）
- "pull 到 ~/Downloads"

Claude Code 会自动识别这些短语并执行对应的 `toss` 命令。

## 两人协作示例

```
你 (Clay-HHK)                         你的协作者 (zhangsan)
──────────────                         ────────────────────────────

1. toss init                           1. toss init
2. toss login --pat                    2. toss login --pat

3. 添加联系人:
   toss contacts add zhangsan \
     --alias laozhang

4. Claude Code 生成了 report.md
   推送:
   toss push report.md laozhang \
     -m "看看结果"
                                       5. 查看收件箱:
                                          toss inbox
                                          > report.md from @Clay-HHK

                                       6. 拉取文件:
                                          toss pull
                                          > Pulled report.md

                                       7. Agent 生成反馈 feedback.md
                                          推回来:
                                          toss push feedback.md Clay-HHK

8. 拉取反馈:
   toss pull
   > Pulled feedback.md
```

## 命令参考

| 命令 | 说明 |
|------|------|
| `toss init` | 初始化 `~/.toss/` 配置目录 |
| `toss login [--pat]` | GitHub 身份认证 |
| `toss logout` | 删除存储的凭据 |
| `toss whoami` | 显示当前身份 |
| `toss contacts add <github> --alias <name>` | 添加联系人 |
| `toss contacts list` | 查看所有联系人 |
| `toss contacts remove <alias>` | 删除联系人 |
| `toss push` | 交互式推送（文件选择器 + 联系人选择器） |
| `toss push <files...> <recipient> [-m msg]` | 直接推送文件给指定收件人 |
| `toss inbox` | 查看待接收文档 |
| `toss pull [--to dir]` | 拉取全部待接收文档 |
| `toss pull --pick` | 交互式选择要拉取的文件 |
| `toss join <server/CODE>` | 加入群组（自动配置一切） |
| `toss group create <name>` | 创建群组 |
| `toss group list` | 查看群组列表 |
| `toss group invite <slug>` | 显示群组邀请码 |
| `toss group join <code>` | 通过邀请码加入群组 |
| `toss group members <slug>` | 查看群组成员 |
| `toss group push <files...> <slug> [-m msg]` | 向群组所有成员推送文件 |
| `toss space create <name> [--slug]` | 创建共享空间 |
| `toss space list` | 查看你的空间 |
| `toss space add-member <slug> <github>` | 添加空间成员 |
| `toss space sync [slug] [--dir .]` | 与空间同步文件 |
| `toss space set-default <slug>` | 设置默认空间 |
| `toss switch <name>` | 切换当前团队（profile） |
| `toss profile list` | 查看所有 profile |
| `toss profile add <name> <url>` | 手动添加 profile |
| `toss profile remove <name>` | 删除 profile |
| `toss init --install-hooks` | 安装 Claude Code hooks |

## 配置

配置文件存储在 `~/.toss/`：

```
~/.toss/
├── config.yaml         # 服务器地址、同步设置
├── credentials.yaml    # JWT 令牌（chmod 600）
└── spaces/             # 共享空间本地文件
```

### config.yaml

```yaml
server:
  base_url: https://toss-api.<your-subdomain>.workers.dev
  timeout: 30
spaces_dir: ~/.toss/spaces
sync:
  auto_sync: false
  sync_interval_seconds: 300
```

## 自部署

你可以在 Cloudflare 上部署自己的 Toss 后端（免费额度足够小团队使用）。

### 前置条件

- [Cloudflare 账号](https://dash.cloudflare.com/sign-up)（免费）
- Node.js 18+

### 部署步骤

```bash
cd worker

# 安装依赖
npm install

# 登录 Cloudflare
npx wrangler login

# 创建资源
npx wrangler d1 create toss-db
npx wrangler r2 bucket create toss-storage
npx wrangler kv namespace create TOSS_KV

# 用上面返回的 ID 更新 wrangler.toml

# 初始化数据库
npx wrangler d1 execute toss-db --remote --file=schema.sql

# 设置 JWT 密钥
openssl rand -hex 32 | npx wrangler secret put JWT_SECRET

# 部署
npx wrangler deploy
```

部署完成后，将 `~/.toss/config.yaml` 中的 `base_url` 改为你的 Worker URL。

## 项目结构

```
toss/
├── src/toss/                    # Python CLI + SDK
│   ├── cli/                     # Click 命令
│   │   ├── main.py              # init, login, whoami, logout, join
│   │   ├── contacts.py          # contacts add/list/remove
│   │   ├── groups.py            # group create/list/invite/join/push
│   │   ├── push_pull.py         # push, pull, inbox（支持交互模式）
│   │   └── spaces.py            # space create/list/sync
│   ├── client/                  # HTTP 客户端 SDK
│   │   ├── base.py              # TossClient (httpx)
│   │   ├── contacts.py          # ContactClient
│   │   ├── documents.py         # DocumentClient
│   │   ├── groups.py            # GroupClient
│   │   └── spaces.py            # SpaceClient
│   ├── sync/                    # 空间同步引擎
│   │   ├── state.py             # 本地清单（SHA-256）
│   │   └── engine.py            # 差异计算 + 上传/下载
│   ├── mcp/                     # MCP 服务
│   │   └── server.py            # FastMCP，10 个工具
│   ├── config/                  # 配置管理
│   │   ├── models.py            # Frozen dataclasses
│   │   └── manager.py           # ConfigManager
│   └── auth/                    # 身份认证
│       ├── github.py            # GitHub PAT + Device Flow
│       └── token_store.py       # JWT 存储
│
├── worker/                      # Cloudflare Worker (TypeScript)
│   ├── src/
│   │   ├── index.ts             # 入口 + 定时清理
│   │   ├── router.ts            # 路由定义
│   │   ├── handlers/            # API 处理器（auth, contacts, documents, groups, spaces, cleanup）
│   │   ├── middleware/          # 认证、CORS、速率限制
│   │   └── services/            # 数据库、存储、GitHub
│   └── schema.sql               # D1 数据库 schema
│
├── npm/                         # npm 包（轻量 wrapper）
│   ├── package.json             # toss-cli npm 包
│   └── bin/toss.js              # 自动安装 uv，通过 uvx 运行
│
├── hooks/                       # Claude Code hooks
│   ├── toss-inbox-check.sh      # 启动时检查收件箱
│   └── toss-sync.sh             # 保存文件时自动同步
│
├── skills/                      # Claude Code skills（自然语言接口）
│   ├── toss-push/skill.md       # "把 report.md 发给 xiaoming"
│   └── toss-pull/skill.md       # "拉取我的收件箱"
│
├── .mcp.json                    # MCP 服务配置
└── pyproject.toml               # Python 项目配置
```

## 路线图

- [x] GitHub 身份认证（PAT + Device Flow）
- [x] 联系人管理（别名系统）
- [x] 文档推送 / 拉取
- [x] 交互式文件选择
- [x] Cloudflare Worker 后端（D1 + R2）
- [x] 共享空间（多人文档同步）
- [x] MCP Server（Claude Code / Cursor 原生集成）
- [x] Claude Code Hooks（保存文件时自动同步）
- [x] 速率限制和文件大小限制
- [x] 过期文档自动清理
- [x] 群组功能（邀请码）
- [x] 零配置加入（`toss join server/CODE`）
- [x] npm 包（`npx toss-cli`）
- [x] 可移植的 hooks 和 MCP 配置（无硬编码路径）
- [x] Claude Code Skills（自然语言推送 / 拉取）
- [x] 多团队 profile 切换
- [ ] 端到端加密
- [ ] Web UI 控制台

## 许可证

MIT
