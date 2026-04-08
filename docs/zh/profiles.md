# 多团队切换

Toss 支持多个服务器 profile，你可以同时加入多个独立团队，用一条命令在它们之间切换，无需重新配置任何东西。

每个 profile 独立存储：
- 服务器地址
- JWT 凭据（每个服务器的 GitHub 身份）

---

## 概念

| 术语 | 含义 |
|------|------|
| **Profile** | 一个命名槽位，存储一个服务器地址和对应凭据 |
| **激活 profile** | 当前所有命令（push、pull、inbox 等）使用的 profile |

---

## 完整流程示例

### 加入第一个团队

```bash
toss join work.example.workers.dev/ABCD-1234
```

输出：
```
Initialized ~/.toss/
Configured profile work -> https://work.example.workers.dev

Login required. Authenticate with GitHub:
  GitHub Personal Access Token: ****
Logged in as clay-hhk
Joined group paper-team

You're all set! Try:
  toss inbox            - check for files
  toss group list       - see your groups
  toss profile list     - see all your teams
  toss switch <name>    - switch between teams
```

### 加入第二个团队

```bash
toss join lab.university.workers.dev/XYZ-9999
```

输出：
```
Configured profile lab -> https://lab.university.workers.dev

Login required. Authenticate with GitHub:
  GitHub Personal Access Token: ****
Logged in as clay-hhk
Joined group ml-lab
```

### 查看所有团队

```bash
toss profile list
```

输出：
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

### 切换团队

```bash
toss switch lab
```

输出：
```
Switched to profile lab
  Server: https://lab.university.workers.dev
  Auth:   logged in as clay-hhk
```

切换后，所有命令（`toss inbox`、`toss push`、`toss group list` 等）都在 `lab` 服务器上操作。

---

## 管理 Profile

### 手动添加

```bash
toss profile add personal https://my-toss.workers.dev
```

然后登录这个 profile：

```bash
toss switch personal
toss login --pat
```

### 删除 profile

删除前必须先切换到其他 profile：

```bash
toss switch work
toss profile remove lab
```

如果尝试删除当前激活的 profile，会报错：

```
Error: Cannot remove active profile 'lab'. Switch to another first.
```

---

## 从 v0.1 升级

如果你之前使用 Toss v0.1，`~/.toss/config.yaml` 里有顶层的 `server:` 字段。v0.2 首次运行时会自动迁移为 `default` profile，无需任何手动操作。

迁移前（v0.1）：
```yaml
server:
  base_url: https://old.workers.dev
  timeout: 30
```

自动迁移后（v0.2）：
```yaml
current_profile: default
profiles:
  default:
    server:
      base_url: https://old.workers.dev
      timeout: 30
```

`credentials.yaml` 中的凭据同样自动迁移。
