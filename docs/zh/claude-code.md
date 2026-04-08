# Claude Code 集成

Toss 与 Claude Code 的集成分三个层次，从轻量到深度：

| 层次 | 作用 | 接入成本 |
|------|------|---------|
| **Skills** | 自然语言触发推送 / 拉取 | 复制 2 个文件 |
| **Hooks** | 自动收件箱检查 + 自动空间同步 | 一条命令 |
| **MCP Server** | Claude 直接调用 Toss 工具（无需 CLI） | 复制一个配置文件 |

---

## Skills（自然语言）

安装 Skills 后，你只需用自然语言描述意图，Claude Code 会自动识别并执行对应命令。

### 安装

```bash
cp -r skills/toss-push skills/toss-pull ~/.claude/skills/
```

### toss-push

触发短语示例：

- `"把 report.md 发给 xiaoming"`
- `"push data.csv 和 notes.md 给 #zhangsan，附言：帮忙看看"`
- `"send analysis.pdf to alice with a note saying check this"`

Claude Code 解析出文件、收件人、附言后，验证文件存在，执行：

```bash
toss push report.md xiaoming -m "帮忙看看"
```

显示结果：
```
Pushed report.md -> xiaoming (2.1KB)
```

### toss-pull

触发短语示例：

- `"拉取我的收件箱"` / `"download files from toss"`
- `"有人给我发东西了吗？"` → 只列出，不下载
- `"pull 到 ~/Downloads"`

**仅列出**（说"查看"、"看看"、"list"、"show"、"what's waiting"时）：

```bash
toss inbox
```

```
                    Inbox (2 pending)
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┓
┃ File         ┃ From        ┃ Size ┃ Message       ┃ Time             ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━┩
│ feedback.md  │ #zhangsan   │ 3.4KB│ looks good    │ 2026-04-08 09:10 │
└──────────────┴─────────────┴──────┴───────────────┴──────────────────┘
```

**下载**（说"拉取"、"下载"、"pull"、"fetch"时）：

```bash
toss pull --to ~/Downloads
```

```
Pulling 1 file(s)...
  Pulled feedback.md (from #zhangsan)
Done. Files saved to /Users/you/Downloads
```

---

## Hooks（自动化）

Hooks 在 Claude Code 特定生命周期事件时自动执行 shell 脚本。

### 安装

```bash
toss init --install-hooks
```

这会向 `~/.claude/settings.json` 写入两条记录：

**SessionStart** — 每次 Claude Code 启动时检查收件箱：

```
Toss inbox: 2 pending
  feedback.md from #zhangsan (3.4KB)
  data.csv from #lisi (15KB)
```

**PostToolUse（Write/Edit）** — 写入共享空间目录中的文件时，自动同步到服务器。

### 手动配置

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

## MCP Server（直接工具调用）

MCP Server 让 Claude Code 把 Toss 当作原生工具调用，无需在终端输入命令。Claude 可以在对话中直接推文件、查收件箱、加入群组。

### 配置

把 `.mcp.json` 复制到你的项目根目录：

```json
{
  "mcpServers": {
    "toss": {
      "command": "toss-mcp"
    }
  }
}
```

需要全局安装 toss（`npm install -g toss-cli` 或 `uv tool install .`）。

### 可用工具（10 个）

| 工具名 | 说明 |
|--------|------|
| `push_document` | 向指定收件人推送文件 |
| `pull_documents` | 下载所有待接收文件 |
| `list_inbox` | 列出待接收文档 |
| `list_contacts` | 查看联系人列表 |
| `add_contact` | 添加联系人 |
| `remove_contact` | 删除联系人 |
| `push_to_group` | 向群组所有成员推送文件 |
| `list_groups` | 查看群组列表 |
| `create_group` | 创建群组 |
| `join_group` | 通过邀请码加入群组 |

### 使用示例

在 Claude Code 对话中说：

> "把最新的 analysis.md 推给 xiaoming，告诉他可以审阅了"

Claude 直接调用 `push_document` 工具，无需你输入任何命令。
