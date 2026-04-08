# Toss

[English](README.md) | [中文](README_CN.md)

**Toss** 是一个命令行工具，让 AI agent 工具用户（Claude Code、Codex、Cursor 等）之间可以直接传文件。不用再通过聊天软件中转，一条命令搞定。

```bash
# 发送文件给协作者
toss push report.md xiaoming -m "帮忙看看"

# 对方一条命令拉取
toss pull
```

## 为什么需要 Toss？

AI agent 工具会生成大量文档，你经常需要分享给协作者。目前的工作流很痛苦：

1. 从 agent 工具导出文件
2. 通过微信 / Slack / 邮件发送
3. 对方下载，拖到自己的工作目录
4. 每轮反馈都重复一遍

**Toss 把这个流程简化为终端里的一条命令。**

## 功能特性

- **推送 / 拉取** — 向任何人发文件，从收件箱下载
- **交互模式** — 文件选择器 + 联系人选择器，不用记参数
- **联系人** — 设置别名（`xiaoming` 代替 `@zhangsan123`）
- **群组** — 一次推送给所有成员，通过邀请码邀请
- **多团队切换** — 同时加入多个团队，`toss switch <name>` 切换
- **共享空间** — 多人文档同步（SHA-256 差异传输，冲突安全）
- **MCP Server** — Claude Code / Cursor 原生调用（10 个工具）
- **Claude Code Hooks** — 启动时自动检查收件箱，保存文件时自动同步
- **Claude Code Skills** — 自然语言："把 report.md 发给 xiaoming"
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
| [快速入门](docs/getting-started.md) | 安装、配置、第一次推送/拉取 |
| [命令速查](docs/cli-reference.md) | 全部命令及示例输出 |
| [多团队切换](docs/profiles.md) | 在不同工作团队之间切换 |
| [Claude Code 集成](docs/claude-code.md) | MCP Server、Hooks、自然语言 Skills |
| [自部署指南](docs/self-hosting.md) | 部署自己的 Cloudflare Worker（免费） |
| [系统架构](docs/architecture.md) | 系统设计与组件说明 |

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
