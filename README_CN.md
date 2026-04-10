# Toss

[English](README.md) | [中文](README_CN.md)

**Toss** 是一个命令行工具，用来传递那些"不属于 git 的产出物"：AI 生成的报告、分析图表、数据集、草稿 PDF 等。一条命令发送，一条命令接收，不用再通过微信中转。

```bash
# 发送文件给协作者
toss push report.md xiaoming -m "帮忙看看"

# 对方一条命令拉取
toss pull
```

> Toss 不是 git 的替代品。代码用 git，产出物用 Toss。

## 使用场景

### 场景 A：AI 产出物传递

AI 工具生成了报告、图表、数据文件，你需要发给不在同一个仓库里的人。

```
  Alice (Claude Code)                    Bob (Cursor)
  ┌───────────────┐                     ┌───────────────┐
  │ Claude 生成了  │   toss push        │               │
  │ report.pdf    │ ──────────────────► │  toss pull    │
  │               │   一条命令           │  → report.pdf │
  └───────────────┘                     └───────────────┘
```

没有 Toss 的流程：导出文件 → 微信/Slack 发送 → 对方下载 → 拖到项目目录（4 步）
有 Toss 的流程：`toss push` → `toss pull`（2 步）

### 场景 B：来回改稿

论文、文档需要在两个人之间反复修改。每轮只需一条命令。

```
  写作者                                   审稿人
  push draft.md ────────────────────►     pull → 读 → 改
                                          push draft_v2.md ──► pull
  push draft_v3.md ────────────────►     pull → 通过
```

### 场景 C：团队广播

负责人需要把数据集或文档一次性发给整个团队。

```
  负责人                                   团队（5 人）
  toss group push dataset.csv ──────────► 5 人都收到
                                           各自 toss pull
```

### 场景 D：共享空间（持久同步）

多人维护一组文件，任何人修改后同步到所有人，类似轻量级 Dropbox。

```
  ┌──────────┐     ┌──────────┐     ┌──────────┐
  │ 成员 A   │────►│  服务器   │◄────│ 成员 B   │
  │ 改 file  │◄────│ SHA-256  │────►│ 改 data  │
  └──────────┘同步  └──────────┘同步  └──────────┘
```

## Toss vs 其他方式

| | 微信/Slack | Git 仓库 | 网盘 | **Toss** |
|---|---|---|---|---|
| **适合内容** | 任意 | 源代码 | 任意 | AI 产出物、文档 |
| **发给谁** | 聊天对象 | 仓库所有人 | 链接持有者 | **指定的人** |
| **操作步骤** | 导出→发送→下载→放到目录 | commit→push→PR | 上传→分享链接→下载 | **一条命令** |
| **终端集成** | 无 | 有 | 无 | **原生** |
| **AI 工具集成** | 无 | 无 | 无 | **MCP/Hooks/Skills** |
| **文件过期** | 手动清理 | 永久 | 手动清理 | **自动过期** |
| **跨团队** | 需要加好友 | 需要仓库权限 | 需要分享 | **同一服务器即可** |

### 什么时候不需要 Toss？

- 团队 3 个人，共享一个 git 仓库，只交换代码 → 用 git 就够了
- 发送大文件（>100MB）→ 用网盘或 `scp`
- 需要永久存档 → 用 git 或网盘

### 什么时候 Toss 最好用？

- 把 Claude Code 生成的分析报告发给导师/产品经理（对方不用 git）
- 论文草稿在两个人之间来回改，每轮一条命令
- 数据集、可视化图表需要发给跨组织的协作者
- 想让 AI 工具直接把结果发给别人，不需要人工中转

## 功能特性

**基础传输**
- **推送 / 拉取** — 向任何人发文件，从收件箱下载
- **交互模式** — 文件选择器 + 联系人选择器，不用记参数
- **联系人** — 设置别名（`xiaoming` 代替 `#zhangsan123`）

**团队协作**
- **群组** — 一次推送给所有成员，通过邀请码加入
- **共享空间** — 多人文档同步（SHA-256 差异传输，冲突安全）
- **多团队切换** — 同时加入多个团队，`toss switch <name>` 切换

**AI 工具集成**
- **MCP Server** — Claude Code / Cursor 原生调用（10 个工具）
- **Claude Code Hooks** — 启动时自动检查收件箱，保存文件时自动同步
- **Claude Code Skills** — 自然语言："把 report.md 发给 xiaoming"

**部署**
- **可自部署** — Cloudflare Worker 后端，免费额度够小团队使用

## 快速开始

如果你收到了团队的邀请码：

```bash
# 不需要 Python
npx toss-cli join toss-api.example.workers.dev/ABCD-1234

# 或者用 uv
uvx --from git+https://github.com/Clay-HHK/toss.git toss join toss-api.example.workers.dev/ABCD-1234
```

一条命令 — 自动配置服务器、登录、加入群组。

> **中国大陆用户**：`workers.dev` 可能需要代理，先运行 `export https_proxy=http://127.0.0.1:7890`。

## 文档

| 文档 | 说明 |
|------|------|
| [快速入门](docs/zh/getting-started.md) | 安装、配置、第一次推送/拉取 |
| [命令速查](docs/zh/cli-reference.md) | 全部命令及示例输出 |
| [多团队切换](docs/zh/profiles.md) | 在不同工作团队之间切换 |
| [Claude Code 集成](docs/zh/claude-code.md) | MCP Server、Hooks、自然语言 Skills |
| [自部署指南](docs/zh/self-hosting.md) | 部署自己的 Cloudflare Worker（免费） |
| [系统架构](docs/zh/architecture.md) | 系统设计与组件说明 |

## 架构

```
CLI (Python)  ──HTTPS──>  Cloudflare Worker (TypeScript)
                              ├── D1  (SQLite: 用户、联系人、文档)
                              ├── R2  (对象存储: 文件内容)
                              └── KV  (缓存: 会话)
```

## 路线图

- [x] GitHub 身份认证（PAT + Device Flow）
- [x] 联系人管理（别名系统）
- [x] 文档推送 / 拉取（含交互模式）
- [x] 群组功能（邀请码 + 零配置加入）
- [x] 共享空间（SHA-256 差异同步）
- [x] MCP Server（10 个工具，Claude Code / Cursor 原生集成）
- [x] Claude Code Hooks（收件箱检查 + 自动同步）
- [x] Claude Code Skills（自然语言推送 / 拉取）
- [x] 多团队 profile 切换
- [x] npm 包（`npx toss-cli`）
- [ ] 端到端加密
- [ ] Web UI 控制台

## 许可证

MIT
