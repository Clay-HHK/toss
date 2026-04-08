# Toss

[English](README.md) | [中文](README_CN.md)

**Toss** is a command-line tool for sharing documents between AI agent tool users (Claude Code, Codex, Cursor, etc.). Instead of manually transferring files through chat apps, just `toss push` and `toss pull`.

```bash
# Send a file to your collaborator
toss push report.md xiaoming -m "please review"

# Recipient pulls it with one command
toss pull
```

## Why Toss?

AI agent tools generate documents you constantly need to share with collaborators. The current workflow is painful:

1. Export file from your agent tool
2. Send via WeChat / Slack / Email
3. Recipient downloads and drags it into their working directory
4. Repeat for every round of feedback

**Toss reduces this to a single terminal command.**

## Features

- **Push / Pull** — send files to anyone, download from your inbox
- **Interactive Mode** — file picker + contact selector, no arguments to remember
- **Contacts** — set aliases (`xiaoming` instead of `@zhangsan123`)
- **Groups** — push to all members at once, invite with a code
- **Multi-Profile** — belong to multiple teams, `toss switch <name>` to change context
- **Shared Spaces** — multi-user document sync (SHA-256 diff, conflict-safe)
- **MCP Server** — Claude Code / Cursor calls Toss natively (10 tools)
- **Claude Code Hooks** — auto inbox check on session start, auto-sync on file save
- **Claude Code Skills** — natural language: "push report.md to xiaoming"
- **Self-hostable** — Cloudflare Worker backend, free tier is enough for small teams

## Quick Start

If you received an invite code from your team:

```bash
# No Python needed
npx toss-cli join toss-api.example.workers.dev/ABCD-1234

# Or with uv
uvx --from git+https://github.com/Clay-HHK/toss.git toss join toss-api.example.workers.dev/ABCD-1234
```

One command — configures server, logs you in, joins the group.

> **Mainland China**: `workers.dev` may need a proxy. Run `export https_proxy=http://127.0.0.1:7890` first.

## Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/getting-started.md) | Install, setup, first push/pull |
| [CLI Reference](docs/cli-reference.md) | Every command with example output |
| [Multi-Team Profiles](docs/profiles.md) | Switch between work teams |
| [Claude Code Integration](docs/claude-code.md) | MCP server, hooks, natural language skills |
| [Self-Hosting](docs/self-hosting.md) | Deploy your own Cloudflare Worker (free) |
| [Architecture](docs/architecture.md) | System design and component overview |

## Architecture

```
CLI (Python)  ──HTTPS──>  Cloudflare Worker (TypeScript)
                              ├── D1  (SQLite: users, contacts, documents)
                              ├── R2  (Object Storage: file content)
                              └── KV  (Cache: sessions)
```

## Roadmap

- [x] GitHub authentication (PAT + Device Flow)
- [x] Contact management with aliases
- [x] Document push / pull with interactive mode
- [x] Groups with invite codes and zero-config join
- [x] Shared Spaces (SHA-256 diff sync)
- [x] MCP Server (10 tools for Claude Code / Cursor)
- [x] Claude Code Hooks (inbox check + auto-sync)
- [x] Claude Code Skills (natural language push/pull)
- [x] Multi-profile support (switch between work teams)
- [x] npm package (`npx toss-cli`)
- [ ] End-to-end encryption
- [ ] Web UI dashboard

## License

MIT
