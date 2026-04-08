# CLI Reference

## Auth

| Command | Description |
|---------|-------------|
| `toss init` | Initialize `~/.toss/` config directory |
| `toss init --install-hooks` | Initialize and install Claude Code hooks |
| `toss login --pat` | Login with GitHub Personal Access Token |
| `toss login` | Login with GitHub Device Flow (browser) |
| `toss logout` | Remove credentials for current profile |
| `toss whoami` | Show identity and active profile |

### `toss whoami` output

```
clay-hhk
  Name:    Han Haoke
  ID:      42
  Profile: work
  Server:  https://work.example.workers.dev
```

---

## Profiles (Multi-Team)

| Command | Description |
|---------|-------------|
| `toss switch <name>` | Switch active profile |
| `toss profile list` | List all profiles |
| `toss profile add <name> <url>` | Add a profile manually |
| `toss profile remove <name>` | Remove a profile (cannot remove the active one) |

### `toss profile list` output

```
          Profiles
┏━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃    ┃ Name     ┃ Server URL                   ┃
┡━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ *  │ work     │ https://work.workers.dev     │
│    │ lab      │ https://lab.workers.dev      │
│    │ personal │ https://personal.workers.dev │
└────┴──────────┴──────────────────────────────┘

Active: work
```

### `toss switch lab` output

```
Switched to profile lab
  Server: https://lab.workers.dev
  Auth:   logged in as clay-hhk
```

See [Multi-Team Profiles](profiles.md) for the full guide.

---

## Contacts

| Command | Description |
|---------|-------------|
| `toss contacts add <github> --alias <name>` | Add a contact |
| `toss contacts list` | List all contacts |
| `toss contacts remove <alias>` | Remove a contact |

Contacts must have run `toss login` at least once on the same server.

### `toss contacts list` output

```
    Contacts
┏━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Alias    ┃ GitHub    ┃
┡━━━━━━━━━━╇━━━━━━━━━━━┩
│ xiaoming │ zhangsan  │
│ laozhao  │ zhaosi    │
└──────────┴───────────┘
```

---

## Push / Pull

| Command | Description |
|---------|-------------|
| `toss push` | Interactive push — file picker + contact selector |
| `toss push <files...> <recipient> [-m msg]` | Direct push |
| `toss inbox` | List pending documents (no download) |
| `toss pull` | Download all pending documents to current directory |
| `toss pull --to <dir>` | Download to a specific directory |
| `toss pull --pick` | Interactively select which files to download |

### `toss inbox` output

```
                    Inbox (2 pending)
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ File         ┃ From        ┃ Size ┃ Message         ┃ Time             ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ report.md    │ #zhangsan   │ 2.1KB│ please review   │ 2026-04-06 10:30 │
│ data.csv     │ #lisi       │ 15KB │                 │ 2026-04-06 09:15 │
└──────────────┴─────────────┴──────┴─────────────────┴──────────────────┘
```

### `toss push report.md xiaoming -m "check this"` output

```
Pushed report.md -> xiaoming (2.1KB)
```

### `toss pull` output

```
Pulling 2 file(s)...
  Pulled report.md (from #zhangsan)
  Pulled data.csv (from #lisi)
Done. Files saved to /Users/you/projects/mywork
```

---

## Groups

| Command | Description |
|---------|-------------|
| `toss join <server/CODE>` | Join a group (auto-configures server + login) |
| `toss group create <name>` | Create a group |
| `toss group list` | List your groups |
| `toss group invite <slug>` | Show the invite code for a group |
| `toss group members <slug>` | List group members |
| `toss group push <files...> <slug> [-m msg]` | Push files to all group members |

### `toss group list` output

```
       Groups
┏━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Name        ┃ Members ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━┩
│ paper-team  │ 3       │
│ lab-collab  │ 2       │
└─────────────┴─────────┘
```

---

## Shared Spaces

| Command | Description |
|---------|-------------|
| `toss space create <name> [--slug]` | Create a shared space |
| `toss space list` | List your spaces |
| `toss space add-member <slug> <github>` | Add a member |
| `toss space sync [slug] [--dir .]` | Sync local directory with a space |
| `toss space set-default <slug>` | Set default space (omit slug in future syncs) |

The sync engine hashes files locally (SHA-256), sends a manifest to the server, and only uploads/downloads changed files. Conflicts are saved as `filename.server.ext`.

---

## Configuration

Config lives in `~/.toss/`:

```
~/.toss/
├── config.yaml         # Profiles + server URLs + sync settings
├── credentials.yaml    # Per-profile JWT tokens (chmod 600)
└── spaces/             # Shared space local files
```

### config.yaml (multi-profile format)

```yaml
current_profile: work
profiles:
  work:
    server:
      base_url: https://work.example.workers.dev
      timeout: 30
  lab:
    server:
      base_url: https://lab.example.workers.dev
      timeout: 30
sync:
  auto_sync: false
  sync_interval_seconds: 300
  ignore_patterns:
    - .DS_Store
    - __pycache__
    - '*.pyc'
    - .git
spaces_dir: ~/.toss/spaces
```

> Old single-server configs (with `server:` at top level) are automatically migrated to a `default` profile on first run.
