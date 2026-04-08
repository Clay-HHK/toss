# Self-Hosting

Toss requires a backend server. The backend is a Cloudflare Worker — it runs on Cloudflare's free tier, which is enough for small teams.

**Free tier limits** (Cloudflare):
- Workers: 100,000 requests/day
- R2: 10 GB storage
- D1: 5 GB database

---

## Prerequisites

- A [Cloudflare account](https://dash.cloudflare.com/sign-up) (free)
- Node.js 18+

---

## Deploy in 5 Minutes

```bash
cd worker

# Install dependencies
npm install

# Login to Cloudflare
npx wrangler login
```

Create the required resources:

```bash
npx wrangler d1 create toss-db
npx wrangler r2 bucket create toss-storage
npx wrangler kv namespace create TOSS_KV
```

Each command prints an ID. Open `worker/wrangler.toml` and fill them in:

```toml
[[d1_databases]]
binding = "DB"
database_name = "toss-db"
database_id = "<paste D1 ID here>"

[[r2_buckets]]
binding = "STORAGE"
bucket_name = "toss-storage"

[[kv_namespaces]]
binding = "KV"
id = "<paste KV ID here>"
```

Apply the database schema and set the JWT secret:

```bash
npx wrangler d1 execute toss-db --remote --file=schema.sql

openssl rand -hex 32 | npx wrangler secret put JWT_SECRET
```

Deploy:

```bash
npx wrangler deploy
```

Output:
```
Deployed toss-worker to https://toss-api.<your-subdomain>.workers.dev
```

---

## Connect Your CLI

```bash
toss init
```

Edit `~/.toss/config.yaml` and set `base_url`:

```yaml
current_profile: default
profiles:
  default:
    server:
      base_url: https://toss-api.<your-subdomain>.workers.dev
```

Then login:

```bash
toss login --pat
toss whoami
```

---

## Invite Your Team

Create a group and share the invite code:

```bash
toss group create my-team
toss group invite my-team
```

Output:
```
Invite code: toss-api.<your-subdomain>.workers.dev/ABCD-1234

Share this with your team. They can join with:
  toss join toss-api.<your-subdomain>.workers.dev/ABCD-1234
```

Recipients run that one command and they're in — no manual config needed.

---

## Limits and Tuning

| Setting | Default | Where |
|---------|---------|-------|
| Rate limit | 60 req/min per user | `worker/src/middleware/rate-limit.ts` |
| Max file size | 100 MB | `worker/src/handlers/documents.ts` |
| Document expiry | 30 days | `worker/src/handlers/cleanup.ts` |

Auto-cleanup runs daily via a Cloudflare cron trigger defined in `wrangler.toml`.
