# Claude Code Integration

Toss integrates with Claude Code in three layers, from lightweight to deep:

| Layer | What it does | Setup effort |
|-------|-------------|--------------|
| **Skills** | Natural language triggers for push/pull | Copy 2 files |
| **Hooks** | Auto inbox check + auto space sync | One command |
| **MCP Server** | Claude calls Toss tools directly (no CLI) | Copy config file |

---

## Skills (Natural Language)

Skills let you operate Toss by describing what you want — Claude Code parses your intent and runs the right command.

### Install

```bash
cp -r skills/toss-push skills/toss-pull ~/.claude/skills/
```

### toss-push

Trigger by saying anything like:

- `"push report.md to xiaoming"`
- `"send data.csv and notes.md to @zhangsan with a note saying check this"`
- `"发给 alice: analysis.pdf"`

Claude Code extracts the files, recipient, and optional message, validates the files exist, then runs:

```bash
toss push report.md xiaoming -m "check this"
```

Output shown to you:
```
Pushed report.md -> xiaoming (2.1KB)
```

### toss-pull

Trigger by saying anything like:

- `"pull my inbox"` / `"下载 toss 里的文件"`
- `"what did people send me?"` → lists without downloading
- `"pull to ~/Downloads"`

**List-only** (when you say "check", "list", "show", "what's waiting"):

```bash
toss inbox
```

```
                    Inbox (2 pending)
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ File         ┃ From        ┃ Size ┃ Message       ┃ Time             ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ feedback.md  │ @zhangsan   │ 3.4KB│ looks good    │ 2026-04-08 09:10 │
└──────────────┴─────────────┴──────┴───────────────┴──────────────────┘
```

**Download** (when you say "pull", "download", "get", "fetch"):

```bash
toss pull --to ~/Downloads
```

```
Pulling 1 file(s)...
  Pulled feedback.md (from @zhangsan)
Done. Files saved to /Users/you/Downloads
```

---

## Hooks (Automatic)

Hooks run shell scripts at specific Claude Code lifecycle events.

### Install

```bash
toss init --install-hooks
```

This writes two entries into `~/.claude/settings.json`:

**SessionStart** — checks your inbox each time Claude Code starts:

```
Toss inbox: 2 pending
  feedback.md from @zhangsan (3.4KB)
  data.csv from @lisi (15KB)
```

**PostToolUse (Write/Edit)** — if you write a file inside a space directory, auto-syncs it to the shared space.

### Manual config (if you prefer)

```json
{
  "hooks": {
    "SessionStart": [
      { "type": "command", "command": "/path/to/toss/hooks/toss-inbox-check.sh" }
    ],
    "PostToolUse": [
      { "type": "command", "command": "/path/to/toss/hooks/toss-sync.sh", "matcher": "Write|Edit" }
    ]
  }
}
```

---

## MCP Server (Direct Tool Calls)

The MCP server lets Claude Code call Toss as a native tool — no terminal command needed. Claude can push files, check inbox, and join groups as part of any conversation.

### Setup

Copy `.mcp.json` to your project root:

```json
{
  "mcpServers": {
    "toss": {
      "command": "toss-mcp"
    }
  }
}
```

Requires `toss` installed globally (`npm install -g toss-cli` or `uv tool install .`).

### Available tools (10)

| Tool | Description |
|------|-------------|
| `push_document` | Push a file to a recipient |
| `pull_documents` | Download all pending inbox files |
| `list_inbox` | List pending documents |
| `list_contacts` | List contacts |
| `add_contact` | Add a contact |
| `remove_contact` | Remove a contact |
| `push_to_group` | Push a file to all group members |
| `list_groups` | List your groups |
| `create_group` | Create a group |
| `join_group` | Join a group by invite code |

### Example

Inside a Claude Code conversation:

> "Push the latest analysis.md to xiaoming and tell them it's ready for review"

Claude calls `push_document` directly — no `toss push` command typed.
