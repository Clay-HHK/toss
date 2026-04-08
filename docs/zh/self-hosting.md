# 自部署指南

Toss 需要一个后端服务器。后端是 Cloudflare Worker，运行在 Cloudflare 免费额度上，足够小团队使用。

**Cloudflare 免费额度**：
- Workers：10 万请求/天
- R2：10 GB 存储
- D1：5 GB 数据库

---

## 前置条件

- [Cloudflare 账号](https://dash.cloudflare.com/sign-up)（免费注册）
- Node.js 18+

---

## 5 分钟完成部署

```bash
cd worker

# 安装依赖
npm install

# 登录 Cloudflare
npx wrangler login
```

创建所需资源：

```bash
npx wrangler d1 create toss-db
npx wrangler r2 bucket create toss-storage
npx wrangler kv namespace create TOSS_KV
```

每条命令都会打印一个 ID。打开 `worker/wrangler.toml`，填入这些 ID：

```toml
[[d1_databases]]
binding = "DB"
database_name = "toss-db"
database_id = "<粘贴 D1 ID>"

[[r2_buckets]]
binding = "STORAGE"
bucket_name = "toss-storage"

[[kv_namespaces]]
binding = "KV"
id = "<粘贴 KV ID>"
```

初始化数据库并设置 JWT 密钥：

```bash
npx wrangler d1 execute toss-db --remote --file=schema.sql

openssl rand -hex 32 | npx wrangler secret put JWT_SECRET
```

部署：

```bash
npx wrangler deploy
```

输出示例：
```
Deployed toss-worker to https://toss-api.<你的子域名>.workers.dev
```

---

## 连接 CLI

```bash
toss init
```

编辑 `~/.toss/config.yaml`，填入 `base_url`：

```yaml
current_profile: default
profiles:
  default:
    server:
      base_url: https://toss-api.<你的子域名>.workers.dev
```

然后登录：

```bash
toss login --pat
toss whoami
```

---

## 邀请团队成员

创建群组并分享邀请码：

```bash
toss group create my-team
toss group invite my-team
```

输出示例：
```
Invite code: toss-api.<你的子域名>.workers.dev/ABCD-1234

Share this with your team. They can join with:
  toss join toss-api.<你的子域名>.workers.dev/ABCD-1234
```

团队成员运行这一条命令即可加入，无需手动配置任何东西。

---

## 限额与调整

| 参数 | 默认值 | 位置 |
|------|--------|------|
| 速率限制 | 60 次请求/分钟/用户 | `worker/src/middleware/rate-limit.ts` |
| 最大文件大小 | 100 MB | `worker/src/handlers/documents.ts` |
| 文档过期时间 | 30 天 | `worker/src/handlers/cleanup.ts` |

自动清理通过 Cloudflare cron trigger 每天运行，配置在 `wrangler.toml` 中。
