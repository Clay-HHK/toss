# 命令速查

## 身份认证

| 命令 | 说明 |
|------|------|
| `toss init` | 初始化 `~/.toss/` 配置目录 |
| `toss init --install-hooks` | 初始化并安装 Claude Code Hooks |
| `toss login --pat` | 用 GitHub Personal Access Token 登录 |
| `toss login` | 用 GitHub Device Flow 登录（浏览器授权） |
| `toss logout` | 删除当前 profile 的凭据 |
| `toss whoami` | 查看当前身份和激活的 profile |

### `toss whoami` 输出示例

```
clay-hhk
  Name:    Han Haoke
  ID:      42
  Profile: work
  Server:  https://work.example.workers.dev
```

---

## Profile（多团队）

| 命令 | 说明 |
|------|------|
| `toss switch <name>` | 切换当前 profile |
| `toss profile list` | 查看所有 profile |
| `toss profile add <name> <url>` | 手动添加 profile |
| `toss profile remove <name>` | 删除 profile（不能删除当前激活的） |

### `toss profile list` 输出示例

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

### `toss switch lab` 输出示例

```
Switched to profile lab
  Server: https://lab.workers.dev
  Auth:   logged in as clay-hhk
```

详见 [多团队切换指南](profiles.md)。

---

## 联系人

| 命令 | 说明 |
|------|------|
| `toss contacts add <github> --alias <name>` | 添加联系人 |
| `toss contacts list` | 查看所有联系人 |
| `toss contacts remove <alias>` | 删除联系人 |

联系人必须在同一个服务器上运行过 `toss login`。

### `toss contacts list` 输出示例

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

## 推送 / 拉取

| 命令 | 说明 |
|------|------|
| `toss push` | 交互模式：文件选择器 + 联系人选择器 |
| `toss push <files...> <recipient> [-m msg]` | 直接推送 |
| `toss inbox` | 查看待接收文档（不下载） |
| `toss pull` | 下载全部待接收文档到当前目录 |
| `toss pull --to <dir>` | 下载到指定目录 |
| `toss pull --pick` | 交互模式：勾选要下载的文件 |

### `toss inbox` 输出示例

```
                    Inbox (2 pending)
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ File         ┃ From        ┃ Size ┃ Message         ┃ Time             ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ report.md    │ @zhangsan   │ 2.1KB│ 帮忙看看        │ 2026-04-06 10:30 │
│ data.csv     │ @lisi       │ 15KB │                 │ 2026-04-06 09:15 │
└──────────────┴─────────────┴──────┴─────────────────┴──────────────────┘
```

### `toss push report.md xiaoming -m "帮忙看看"` 输出示例

```
Pushed report.md -> xiaoming (2.1KB)
```

### `toss pull` 输出示例

```
Pulling 2 file(s)...
  Pulled report.md (from @zhangsan)
  Pulled data.csv (from @lisi)
Done. Files saved to /Users/you/projects/mywork
```

---

## 群组

| 命令 | 说明 |
|------|------|
| `toss join <server/CODE>` | 加入群组（自动配置服务器 + 登录） |
| `toss group create <name>` | 创建群组 |
| `toss group list` | 查看群组列表 |
| `toss group invite <slug>` | 显示群组邀请码 |
| `toss group members <slug>` | 查看群组成员 |
| `toss group push <files...> <slug> [-m msg]` | 向群组所有成员推送文件 |

### `toss group list` 输出示例

```
       Groups
┏━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Name        ┃ Members ┃
┡━━━━━━━━━━━━━╇━━━━━━━━━┩
│ paper-team  │ 3       │
│ lab-collab  │ 2       │
└─────────────┴─────────┘
```

### `toss group invite paper-team` 输出示例

```
Invite code: toss-api.example.workers.dev/ABCD-1234

Share this with your team. They can join with:
  toss join toss-api.example.workers.dev/ABCD-1234
```

---

## 共享空间

| 命令 | 说明 |
|------|------|
| `toss space create <name> [--slug]` | 创建共享空间 |
| `toss space list` | 查看你的空间 |
| `toss space add-member <slug> <github>` | 添加成员 |
| `toss space sync [slug] [--dir .]` | 与空间同步文件 |
| `toss space set-default <slug>` | 设置默认空间（之后可省略 slug） |

同步引擎在本地计算 SHA-256 哈希，只传输有变化的文件。冲突文件保存为 `filename.server.ext`，需手动解决。

---

## 配置文件

配置存储在 `~/.toss/`：

```
~/.toss/
├── config.yaml         # Profile 列表 + 服务器地址 + 同步设置
├── credentials.yaml    # 各 profile 的 JWT 令牌（chmod 600）
└── spaces/             # 共享空间本地文件
```

### config.yaml（多 profile 格式）

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

> 旧版（v0.1）的单服务器配置（顶层有 `server:` 字段）会在首次运行时自动迁移为 `default` profile，无需手动操作。
