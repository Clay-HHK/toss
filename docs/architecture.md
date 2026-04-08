# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────┐
│  Client side                                            │
│                                                         │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────┐  │
│  │  Python CLI  │   │  MCP Server  │   │   Skills   │  │
│  │  (toss push) │   │ (toss-mcp)   │   │ (NL input) │  │
│  └──────┬───────┘   └──────┬───────┘   └─────┬──────┘  │
│         └──────────────────┴─────────────────┘         │
│                            │ HTTPS                      │
└────────────────────────────┼────────────────────────────┘
                             │
┌────────────────────────────┼────────────────────────────┐
│  Cloudflare Edge           │                            │
│                            ▼                            │
│              ┌─────────────────────────┐                │
│              │   Cloudflare Worker     │                │
│              │   (TypeScript)          │                │
│              │                         │                │
│              │  Auth ── CORS ── Rate   │                │
│              │  limiting middleware    │                │
│              │                         │                │
│              │  /api/v1/documents  ────┼──► R2 Storage  │
│              │  /api/v1/contacts   ────┼──► D1 (SQLite) │
│              │  /api/v1/groups     ────┼──► D1 (SQLite) │
│              │  /api/v1/spaces     ────┼──► R2 + D1     │
│              │  /api/v1/auth       ────┼──► GitHub API  │
│              └─────────────────────────┘                │
└─────────────────────────────────────────────────────────┘
```

---

## Components

### Python CLI (`src/toss/`)

| Module | Purpose |
|--------|---------|
| `cli/` | Click command definitions (push, pull, contacts, groups, spaces, profiles) |
| `client/` | HTTP client SDK wrapping the Worker API (httpx-based) |
| `config/` | Config file management — multi-profile YAML read/write, migration |
| `auth/` | GitHub PAT and Device Flow authentication, JWT storage |
| `sync/` | SHA-256 manifest diffing for shared spaces |
| `mcp/` | FastMCP server exposing 10 Toss tools to Claude Code / Cursor |

### Cloudflare Worker (`worker/`)

| Module | Purpose |
|--------|---------|
| `handlers/` | API route handlers — documents, contacts, groups, spaces, auth, cleanup |
| `middleware/` | JWT auth check, CORS headers, rate limiting (60 req/min/user) |
| `services/` | Database (D1), object storage (R2), GitHub API client |
| `schema.sql` | D1 table definitions |

### Storage

| Store | What lives there |
|-------|-----------------|
| **R2** | File contents (binary blobs, keyed by document ID) |
| **D1** | Users, contacts, documents metadata, groups, spaces |
| **KV** | Session cache (optional, for future use) |

---

## Authentication Flow

```
User                CLI                  Worker            GitHub
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
 │  (JWT stored in   │                     │                  │
 │  credentials.yaml)│                     │                  │
```

All subsequent requests include `Authorization: Bearer <jwt>`. The Worker validates the JWT (signed with `JWT_SECRET`) on every request.

---

## Multi-Profile Config

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
      my-proj/   ← local space files
```

`ConfigManager` selects the active profile from `current_profile`, returning the correct server URL and JWT to all callers. Old flat configs (v0.1) are transparently migrated to a `default` profile.

---

## Document Lifecycle

```
push
 └─► Worker stores metadata in D1 (filename, sender, recipient, size, expires_at)
 └─► Worker stores content in R2 (key: document_id)

inbox
 └─► Worker queries D1 for documents where recipient = me AND pulled = false

pull
 └─► Worker streams R2 content → client writes to disk
 └─► Worker marks document pulled = true in D1

cleanup (daily cron)
 └─► Worker deletes D1 rows where expires_at < now
 └─► Worker deletes corresponding R2 objects
```

---

## Project Structure

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
│   │   ├── models.py            # Frozen dataclasses (ServerConfig, TossConfig)
│   │   └── manager.py           # Multi-profile config + migration
│   ├── auth/
│   │   ├── github.py            # PAT + Device Flow
│   │   └── token_store.py       # Per-profile JWT storage
│   ├── sync/
│   │   ├── state.py             # Local manifest (SHA-256)
│   │   └── engine.py            # Diff + upload/download
│   └── mcp/
│       └── server.py            # FastMCP, 10 tools
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
├── npm/                         # npm wrapper (toss-cli)
├── hooks/                       # Claude Code hooks
├── skills/                      # Claude Code skills
├── docs/                        # This documentation
├── .mcp.json
└── pyproject.toml
```
