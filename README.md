# Toss

[English](README.md) | [中文](README_CN.md)

**Toss** is a command-line tool for sharing documents between AI agent tool users (Claude Code, Codex, Cursor, etc.). Instead of manually transferring files through chat apps, just `toss push` and `toss pull`.

```
# Send a file to your collaborator
toss push report.md xiaoming -m "please review"

# Or use interactive mode - just type toss push
toss push
# → Select files → Pick recipient → Add message → Done!

# Recipient pulls it with one command
toss pull
```

## Why Toss?

AI agent tools like Claude Code and Codex generate documents (analysis reports, code files, configs) that you often need to share with collaborators. The current workflow is painful:

1. Export file from your agent tool
2. Send via WeChat/Slack/Email
3. Recipient downloads the file
4. Drags it into their agent tool's directory
5. Repeat for every round of feedback

**Toss reduces this to a single command in your terminal.** No context switching, no file dragging, no chat app juggling.

## Features

- **Push/Pull**: Send files to anyone, pull from your inbox
- **Interactive Mode**: File picker, contact selector, no need to remember arguments
- **Contacts**: Set aliases for frequent collaborators (`xiaoming` instead of `@zhangsan123`)
- **Inbox**: Check what's waiting for you without downloading
- **Shared Spaces** (coming soon): Multiple users read/write to a shared document collection
- **MCP Server** (coming soon): Let Claude Code/Cursor call Toss tools natively
- **Claude Code Hooks** (coming soon): Auto-sync on file save

## Architecture

```
CLI (Python)  ──HTTPS──>  Cloudflare Worker (TypeScript)
                              ├── D1 (SQLite DB: users, contacts, documents)
                              ├── R2 (Object Storage: file content)
                              └── KV (Cache: sessions)
```

- **Backend**: Cloudflare Workers (free tier: 100K requests/day)
- **Storage**: R2 (free tier: 10GB) for documents, D1 (free tier: 5GB) for metadata
- **Auth**: GitHub identity + JWT tokens

## Quick Start

> **Important**: Toss requires a backend server. Each team/group needs to deploy their own
> Cloudflare Worker (free). See [Self-Hosting](#self-hosting) below for the 5-minute setup.

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- A GitHub account
- A GitHub Personal Access Token ([create one here](https://github.com/settings/tokens), select `read:user` scope)

### 1. Deploy Backend (one person per team)

Follow the [Self-Hosting](#self-hosting) section to deploy your own Cloudflare Worker. You will get a URL like `https://toss-api.<your-subdomain>.workers.dev`.

### 2. Install CLI (everyone)

```bash
# Clone the repo
git clone https://github.com/Clay-HHK/toss.git
cd toss

# Install with uv
uv sync

# Initialize config
uv run toss init

# Set your team's server URL
# Edit ~/.toss/config.yaml and set base_url to your Worker URL

# Login with your GitHub PAT
uv run toss login --pat
# Paste your token when prompted

# Verify
uv run toss whoami
```

### Network Note (China)

If you are in mainland China, `workers.dev` may require a proxy. Set the proxy before running toss commands:

```bash
export https_proxy=http://127.0.0.1:7890
```

Or add it to your shell profile (`~/.zshrc`).

## Usage

### Login

```bash
# Login with GitHub Personal Access Token
toss login --pat

# Check current identity
toss whoami

# Logout
toss logout
```

### Contacts

Set up aliases for your collaborators. They must have run `toss login` at least once.

```bash
# Add a contact with an alias
toss contacts add zhangsan --alias xiaoming

# List all contacts
toss contacts list

# Remove a contact
toss contacts remove xiaoming
```

### Push Files

Send one or more files to a collaborator.

```bash
# Interactive mode (recommended for beginners)
toss push
# → Shows file picker (Space to select, Enter to confirm)
# → Shows contact list or manual input
# → Optional message prompt
# → Files sent!

# Direct mode - push a single file (by alias)
toss push report.md xiaoming

# Push with a message
toss push report.md xiaoming -m "please review section 3"

# Push multiple files
toss push data.csv analysis.md xiaoming

# Push to someone by GitHub username (no alias needed)
toss push report.md @zhangsan
```

### Check Inbox

See what files are waiting for you.

```bash
toss inbox
```

Output:
```
                    Inbox (2 pending)
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ File         ┃ From        ┃ Size ┃ Message         ┃ Time             ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ report.md    │ @zhangsan   │ 2.1KB│ please review   │ 2026-04-06 10:30 │
│ data.csv     │ @lisi       │ 15KB │                 │ 2026-04-06 09:15 │
└──────────────┴─────────────┴──────┴─────────────────┴──────────────────┘
```

### Pull Files

Download files from your inbox.

```bash
# Pull everything to current directory
toss pull

# Pull to a specific directory
toss pull --to ~/Downloads/toss

# Interactive mode - select which files to pull
toss pull --pick
# → Shows checkbox with file list (name, size, sender)
# → Space to select, Enter to confirm
# → Choose download destination
# → Selected files downloaded!
```

## Two-Person Collaboration Example

```
You (Clay-HHK)                         Your Collaborator (zhangsan)
──────────────                         ────────────────────────────

1. toss init                           1. toss init
2. toss login --pat                    2. toss login --pat

3. Add contact:
   toss contacts add zhangsan \
     --alias laozhang

4. Claude Code generates report.md
   Push it:
   toss push report.md laozhang \
     -m "check the results"
                                       5. Check inbox:
                                          toss inbox
                                          > report.md from @Clay-HHK

                                       6. Pull the file:
                                          toss pull
                                          > Pulled report.md

                                       7. Agent reviews, generates feedback.md
                                          Push back:
                                          toss push feedback.md Clay-HHK

8. Pull feedback:
   toss pull
   > Pulled feedback.md
```

## CLI Reference

| Command | Description |
|---------|-------------|
| `toss init` | Initialize `~/.toss/` config directory |
| `toss login [--pat]` | Authenticate with GitHub |
| `toss logout` | Remove stored credentials |
| `toss whoami` | Show current identity |
| `toss contacts add <github> --alias <name>` | Add a contact |
| `toss contacts list` | List all contacts |
| `toss contacts remove <alias>` | Remove a contact |
| `toss push` | Interactive push (file picker + contact selector) |
| `toss push <files...> <recipient> [-m msg]` | Direct push files to a recipient |
| `toss inbox` | List pending documents |
| `toss pull [--to dir]` | Pull all pending documents |
| `toss pull --pick` | Interactively select which files to pull |

## Configuration

Config is stored in `~/.toss/`:

```
~/.toss/
├── config.yaml         # Server URL, sync settings
├── credentials.yaml    # JWT token (chmod 600)
└── spaces/             # Shared space files (coming soon)
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

## Self-Hosting

You can deploy your own Toss backend on Cloudflare (free tier).

### Prerequisites

- A [Cloudflare account](https://dash.cloudflare.com/sign-up) (free)
- Node.js 18+

### Deploy

```bash
cd worker

# Install dependencies
npm install

# Login to Cloudflare
npx wrangler login

# Create resources
npx wrangler d1 create toss-db
npx wrangler r2 bucket create toss-storage
npx wrangler kv namespace create TOSS_KV

# Update wrangler.toml with the IDs returned above

# Apply database schema
npx wrangler d1 execute toss-db --remote --file=schema.sql

# Set JWT secret
openssl rand -hex 32 | npx wrangler secret put JWT_SECRET

# Deploy
npx wrangler deploy
```

After deployment, update `~/.toss/config.yaml` to point `base_url` to your Worker URL.

## Project Structure

```
toss/
├── src/toss/                    # Python CLI + SDK
│   ├── cli/                     # Click commands
│   │   ├── main.py              # init, login, whoami, logout
│   │   ├── contacts.py          # contacts add/list/remove
│   │   └── push_pull.py         # push, pull, inbox
│   ├── client/                  # HTTP client SDK
│   │   ├── base.py              # TossClient (httpx)
│   │   ├── contacts.py          # ContactClient
│   │   └── documents.py         # DocumentClient
│   ├── config/                  # Configuration
│   │   ├── models.py            # Frozen dataclasses
│   │   └── manager.py           # ConfigManager
│   └── auth/                    # Authentication
│       ├── github.py            # GitHub PAT + Device Flow
│       └── token_store.py       # JWT storage
│
├── worker/                      # Cloudflare Worker (TypeScript)
│   ├── src/
│   │   ├── index.ts             # Entry point
│   │   ├── router.ts            # Route definitions
│   │   ├── handlers/            # API handlers
│   │   ├── middleware/          # Auth, CORS
│   │   └── services/            # DB, Storage, GitHub
│   └── schema.sql               # D1 database schema
│
└── pyproject.toml               # Python project config
```

## Roadmap

- [x] GitHub authentication (PAT + Device Flow)
- [x] Contact management with aliases
- [x] Document push/pull
- [x] Interactive file selection
- [x] Cloudflare Worker backend (D1 + R2)
- [ ] Shared Spaces (multi-user document sync)
- [ ] MCP Server (Claude Code / Cursor native integration)
- [ ] Claude Code Hooks (auto-sync on file save)
- [ ] End-to-end encryption
- [ ] Web UI dashboard

## License

MIT
