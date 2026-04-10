# 快速入门

## 前置条件

- GitHub 账号
- GitHub Personal Access Token — [点此创建](https://github.com/settings/tokens)，只需勾选 `read:user` 权限
- 一个 Toss 服务器地址（收到别人的邀请码，或者[自己部署](self-hosting.md)）

> **中国大陆用户**：`workers.dev` 域名可能需要代理。在运行任何 `toss` 命令前，先执行 `export https_proxy=http://127.0.0.1:7890`，或者写入 `~/.zshrc`。

---

## 安装

**方式 A — npm（推荐，不需要 Python）**

```bash
npm install -g toss-cli
toss --version
```

**方式 B — uv**

```bash
uv tool install git+https://github.com/Clay-HHK/toss.git
toss --version
```

**方式 C — Docker（全平台）**

```bash
docker pull ghcr.io/clay-hhk/toss:latest

# 添加别名方便使用（写入 ~/.bashrc 或 ~/.zshrc）
alias toss='docker run --rm -v ~/.toss:/root/.toss -v $(pwd):/work ghcr.io/clay-hhk/toss:latest'

toss --version
```

Windows、Linux、macOS 都能用，不需要装 Python 或 Node.js。

**方式 D — 从源码安装**

```bash
git clone https://github.com/Clay-HHK/toss.git
cd toss && uv tool install .
```

---

## 加入团队（最简单的方式）

如果别人已经部署好了 Toss 服务并给了你邀请码，一条命令完成所有配置 — 自动设置服务器、登录、加入群组：

```bash
toss join toss-api.example.workers.dev/ABCD-1234
```

输出示例：
```
Initialized ~/.toss/
Configured profile toss-api -> https://toss-api.example.workers.dev

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

或者通过 npx，不需要提前安装：

```bash
npx toss-cli join toss-api.example.workers.dev/ABCD-1234
```

---

## 手动配置

如果你是第一个部署服务器的人，或者不使用邀请码：

```bash
# 1. 初始化配置目录
toss init

# 2. 编辑 ~/.toss/config.yaml，填入你的 Worker 地址
#    current_profile: default
#    profiles:
#      default:
#        server:
#          base_url: https://toss-api.<你的子域名>.workers.dev

# 3. 用 GitHub PAT 登录
toss login --pat

# 4. 验证身份
toss whoami
```

`toss whoami` 输出示例：
```
clay-hhk
  Name:    Han Haoke
  ID:      42
  Profile: default
  Server:  https://toss-api.<你的子域名>.workers.dev
```

---

## 发送第一个文件

```bash
# 添加联系人（对方必须先运行过 toss login）
toss contacts add zhangsan --alias xiaoming

# 推送文件
toss push report.md xiaoming -m "帮忙看看"

# 输出：
# Pushed report.md -> xiaoming (2.1KB)

# 对方拉取
toss pull
# 输出：
# Pulling 1 file(s)...
#   Pulled report.md (from #clay-hhk)
# Done. Files saved to /Users/zhangsan/projects
```

或者用**交互模式**，完全不用记参数：

```bash
toss push
# → 文件选择器（空格选择，回车确认）
# → 联系人列表或手动输入
# → 可选附言
# → 发送完成！

toss pull --pick
# → 文件列表（勾选要下载的）
# → 选择保存位置
# → 下载完成！
```

---

## 下一步

- [命令速查](cli-reference.md) — 所有命令和示例输出
- [多团队切换](profiles.md) — 同时加入多个团队，一键切换
- [Claude Code 集成](claude-code.md) — MCP Server、Hooks、自然语言 Skills
- [自部署指南](self-hosting.md) — 部署自己的 Cloudflare Worker（免费）
