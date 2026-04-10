# Getting Started

## Prerequisites

- A GitHub account
- A GitHub Personal Access Token — [create one here](https://github.com/settings/tokens), select the `read:user` scope only
- A Toss server URL (either someone's invite code, or [deploy your own](self-hosting.md))

> **Mainland China users**: `workers.dev` may need a proxy. Set `export https_proxy=http://127.0.0.1:7890` before running any `toss` command, or add it to your `~/.zshrc`.

---

## Install

**Option A — npm (recommended, no Python needed)**

```bash
npm install -g toss-cli
toss --version
```

**Option B — uv**

```bash
uv tool install git+https://github.com/Clay-HHK/toss.git
toss --version
```

**Option C — Docker (any platform)**

```bash
docker pull ghcr.io/clay-hhk/toss:latest

# Add an alias for convenience (add to ~/.bashrc or ~/.zshrc)
alias toss='docker run --rm -v ~/.toss:/root/.toss -v $(pwd):/work ghcr.io/clay-hhk/toss:latest'

toss --version
```

Works on Windows, Linux, and macOS — no Python or Node.js needed.

**Option D — from source**

```bash
git clone https://github.com/Clay-HHK/toss.git
cd toss && uv tool install .
```

---

## Join a Team (easiest path)

If someone already has a Toss server and gave you an invite code, one command does everything — configures the server, logs you in, and joins the group:

```bash
toss join toss-api.example.workers.dev/ABCD-1234
```

Or via npx without installing:

```bash
npx toss-cli join toss-api.example.workers.dev/ABCD-1234
```

---

## Manual Setup

If you are setting up your own server (or joining without an invite code):

```bash
# 1. Initialize config directory
toss init

# 2. Edit ~/.toss/config.yaml and set base_url to your Worker URL
#    current_profile: default
#    profiles:
#      default:
#        server:
#          base_url: https://toss-api.<your-subdomain>.workers.dev

# 3. Login with your GitHub PAT
toss login --pat

# 4. Verify identity
toss whoami
```

---

## Send Your First File

```bash
# Add a contact (they must have run toss login at least once)
toss contacts add zhangsan --alias xiaoming

# Push a file
toss push report.md xiaoming -m "please review"

# Recipient pulls it
toss pull
```

Or use **interactive mode** — no arguments needed:

```bash
toss push
# → file picker → contact selector → optional message → sent!

toss pull --pick
# → checkbox list → choose destination → downloaded!
```

---

## Next Steps

- [CLI Reference](cli-reference.md) — every command and flag
- [Multi-Team Profiles](profiles.md) — belong to multiple teams, switch instantly
- [Claude Code Integration](claude-code.md) — MCP server, hooks, natural language skills
- [Self-Hosting](self-hosting.md) — deploy your own Cloudflare Worker (free)
