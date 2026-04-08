# Multi-Team Profiles

Toss supports multiple server profiles, so you can belong to several independent teams and switch between them with a single command — without re-configuring anything.

Each profile stores its own:
- Server URL
- JWT credentials (GitHub identity per server)

---

## Concepts

| Term | Meaning |
|------|---------|
| **Profile** | A named slot storing one server URL + its credentials |
| **Active profile** | The profile all commands (`push`, `pull`, `inbox`, etc.) currently use |

---

## Typical Workflow

### Join your first team

```bash
toss join work.example.workers.dev/ABCD-1234
```

Output:
```
Initialized ~/.toss/
Configured profile work -> https://work.example.workers.dev
Logged in as clay-hhk
Joined group paper-team

You're all set! Try:
  toss inbox            - check for files
  toss group list       - see your groups
  toss profile list     - see all your teams
  toss switch <name>    - switch between teams
```

### Join a second team

```bash
toss join lab.university.workers.dev/XYZ-9999
```

Output:
```
Configured profile lab -> https://lab.university.workers.dev

Login required. Authenticate with GitHub:
  GitHub Personal Access Token: ****
Logged in as clay-hhk
Joined group ml-lab
```

### See all teams

```bash
toss profile list
```

Output:
```
          Profiles
┏━━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃    ┃ Name ┃ Server URL                         ┃
┡━━━━╇━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ *  │ work │ https://work.example.workers.dev   │
│    │ lab  │ https://lab.university.workers.dev │
└────┴──────┴────────────────────────────────────┘

Active: work
```

### Switch teams

```bash
toss switch lab
```

Output:
```
Switched to profile lab
  Server: https://lab.university.workers.dev
  Auth:   logged in as clay-hhk
```

All subsequent commands now operate on the `lab` server — `toss inbox`, `toss push`, `toss group list`, etc.

---

## Managing Profiles

### Add a profile manually

```bash
toss profile add personal https://my-toss.workers.dev
```

Then login to that profile:

```bash
toss switch personal
toss login --pat
```

### Remove a profile

You must switch away from a profile before removing it:

```bash
toss switch work
toss profile remove lab
```

Attempting to remove the active profile fails with:

```
Error: Cannot remove active profile 'lab'. Switch to another first.
```

---

## Migration from v0.1

If you used Toss before v0.2, your existing `~/.toss/config.yaml` had a flat `server:` block. On first run of v0.2+, it is automatically migrated to a `default` profile — no manual action needed.

Before (v0.1):
```yaml
server:
  base_url: https://old.workers.dev
  timeout: 30
```

After automatic migration (v0.2):
```yaml
current_profile: default
profiles:
  default:
    server:
      base_url: https://old.workers.dev
      timeout: 30
```

Credentials in `credentials.yaml` are migrated the same way.
