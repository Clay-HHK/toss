# Toss

[English](README.md) | [中文](README_CN.md)

**Toss** is a command-line tool for sharing artifacts that don't belong in git: AI-generated reports, analysis charts, datasets, draft PDFs, and more. One command to send, one command to receive. No more dragging files through chat apps.

```bash
# Send a file to your collaborator
toss push report.md xiaoming -m "please review"

# Recipient pulls it with one command
toss pull
```

> Toss is not a git replacement. Use git for code, Toss for artifacts.

## Use Cases

### Case A: Sharing AI-generated artifacts

Your AI tool produced a report, chart, or dataset. You need to send it to someone who isn't in the same repo.

```
  Alice (Claude Code)                    Bob (Cursor)
  ┌───────────────┐                     ┌───────────────┐
  │ Claude made   │   toss push         │               │
  │ report.pdf    │ ──────────────────► │  toss pull    │
  │               │   one command        │  → report.pdf │
  └───────────────┘                     └───────────────┘
```

Without Toss: export file → send via Slack/WeChat → download → drag into project dir (4 steps)
With Toss: `toss push` → `toss pull` (2 steps)

### Case B: Iterative review

A paper or document goes back and forth between two people. Each round takes one command.

```
  Writer                                   Reviewer
  push draft.md ────────────────────►     pull → read → edit
                                          push draft_v2.md ──► pull
  push draft_v3.md ────────────────►     pull → approve
```

### Case C: Team broadcast

A lead needs to send a dataset or document to the entire team at once.

```
  Lead                                     Team (5 people)
  toss group push dataset.csv ──────────► all 5 receive it
                                           each runs: toss pull
```

### Case D: Shared space (persistent sync)

Multiple people maintain a set of files, synced to everyone on change. Like a lightweight Dropbox.

```
  ┌──────────┐     ┌──────────┐     ┌──────────┐
  │ Member A │────►│  Server  │◄────│ Member B │
  │ edit     │◄────│ SHA-256  │────►│ edit     │
  │ file.md  │sync └──────────┘sync │ data.csv │
  └──────────┘                      └──────────┘
```

## Toss vs Other Approaches

| | Chat apps | Git repo | Cloud drive | **Toss** |
|---|---|---|---|---|
| **Best for** | Anything | Source code | Anything | AI artifacts, docs |
| **Recipient** | Chat contact | Everyone on repo | Link holder | **Specific person** |
| **Steps** | Export→send→download→move | commit→push→PR | Upload→share link→download | **One command** |
| **Terminal native** | No | Yes | No | **Yes** |
| **AI tool integration** | No | No | No | **MCP/Hooks/Skills** |
| **File expiry** | Manual cleanup | Permanent | Manual cleanup | **Auto-expires** |
| **Cross-org** | Need to add contact | Need repo access | Need sharing | **Same server is enough** |

### When you don't need Toss

- 3-person team sharing a git repo, exchanging only code → git is enough
- Large files (>100MB) → use cloud storage or `scp`
- Need permanent archival → use git or cloud storage

### When Toss shines

- Sending a Claude Code analysis report to your advisor or PM (who doesn't use git)
- Paper drafts going back and forth, one command per round
- Datasets and visualizations shared with cross-org collaborators
- Letting AI tools send results to people directly, no manual relay

## Features

**Basic Transfer**
- **Push / Pull** — send files to anyone, download from your inbox
- **Interactive Mode** — file picker + contact selector, no arguments to remember
- **Contacts** — set aliases (`xiaoming` instead of `#zhangsan123`)

**Team Collaboration**
- **Groups** — push to all members at once, invite with a code
- **Shared Spaces** — multi-user document sync (SHA-256 diff, conflict-safe)
- **Multi-Profile** — belong to multiple teams, `toss switch <name>` to change context

**AI Tool Integration**
- **MCP Server** — Claude Code / Cursor calls Toss natively (10 tools)
- **Claude Code Hooks** — auto inbox check on session start, auto-sync on file save
- **Claude Code Skills** — natural language: "push report.md to xiaoming"

**Deployment**
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
