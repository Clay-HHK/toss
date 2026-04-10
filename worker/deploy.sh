#!/usr/bin/env bash
#
# Toss Server — One-click deployment to Cloudflare Workers
#
# Usage:
#   cd worker && bash deploy.sh
#
# Prerequisites:
#   - Node.js 18+
#   - A Cloudflare account (free tier is enough)
#
# What this script does:
#   1. Install npm dependencies
#   2. Login to Cloudflare (if not already logged in)
#   3. Create D1 database, R2 bucket, KV namespace
#   4. Write resource IDs into wrangler.toml
#   5. Apply database schema
#   6. Generate and set JWT secret
#   7. Deploy the Worker
#
set -euo pipefail

# ── Colors ──────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

info()  { echo -e "${CYAN}[INFO]${NC}  $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC}  $*"; }
fail()  { echo -e "${RED}[FAIL]${NC}  $*"; exit 1; }

# ── Pre-checks ──────────────────────────────────────────────
command -v node  >/dev/null 2>&1 || fail "Node.js is required. Install: https://nodejs.org/"
command -v npm   >/dev/null 2>&1 || fail "npm is required. Install: https://nodejs.org/"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -f "package.json" ]; then
    fail "Must run from the worker/ directory (or the script does it automatically)."
fi

info "Starting Toss server deployment..."
echo ""

# ── Step 1: npm install ─────────────────────────────────────
info "Step 1/7: Installing dependencies..."
npm install --silent
ok "Dependencies installed."

# ── Step 2: Cloudflare login ────────────────────────────────
info "Step 2/7: Checking Cloudflare login..."
if npx wrangler whoami 2>/dev/null | grep -q "You are logged in"; then
    ok "Already logged in to Cloudflare."
else
    info "Opening browser for Cloudflare login..."
    npx wrangler login
    ok "Cloudflare login complete."
fi

# ── Step 3: Create resources ────────────────────────────────
info "Step 3/7: Creating Cloudflare resources..."

# D1 database
D1_OUTPUT=$(npx wrangler d1 create toss-db 2>&1) || true
if echo "$D1_OUTPUT" | grep -q "already exists"; then
    warn "D1 database 'toss-db' already exists, skipping."
    D1_ID=$(npx wrangler d1 list 2>&1 | grep "toss-db" | awk '{print $1}')
else
    D1_ID=$(echo "$D1_OUTPUT" | grep -oP 'database_id\s*=\s*"\K[^"]+' || \
            echo "$D1_OUTPUT" | grep -oE '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' | head -1)
fi
if [ -z "${D1_ID:-}" ]; then
    fail "Could not extract D1 database ID. Output:\n$D1_OUTPUT"
fi
ok "D1 database: $D1_ID"

# R2 bucket
R2_OUTPUT=$(npx wrangler r2 bucket create toss-storage 2>&1) || true
if echo "$R2_OUTPUT" | grep -q "already exists"; then
    warn "R2 bucket 'toss-storage' already exists, skipping."
else
    ok "R2 bucket created."
fi

# KV namespace
KV_OUTPUT=$(npx wrangler kv namespace create TOSS_KV 2>&1) || true
if echo "$KV_OUTPUT" | grep -q "already exists"; then
    warn "KV namespace 'TOSS_KV' already exists, skipping."
    KV_ID=$(npx wrangler kv namespace list 2>&1 | grep -A1 "TOSS_KV" | grep -oE '[0-9a-f]{32}' | head -1)
else
    KV_ID=$(echo "$KV_OUTPUT" | grep -oP 'id\s*=\s*"\K[^"]+' || \
            echo "$KV_OUTPUT" | grep -oE '[0-9a-f]{32}' | head -1)
fi
if [ -z "${KV_ID:-}" ]; then
    fail "Could not extract KV namespace ID. Output:\n$KV_OUTPUT"
fi
ok "KV namespace: $KV_ID"

# ── Step 4: Update wrangler.toml ────────────────────────────
info "Step 4/7: Writing resource IDs to wrangler.toml..."

# Back up original
cp wrangler.toml wrangler.toml.bak

sed -i.tmp "s|database_id = \"<YOUR_D1_DATABASE_ID>\"|database_id = \"$D1_ID\"|" wrangler.toml
sed -i.tmp "s|id = \"<YOUR_KV_NAMESPACE_ID>\"|id = \"$KV_ID\"|" wrangler.toml
rm -f wrangler.toml.tmp

ok "wrangler.toml updated (backup: wrangler.toml.bak)."

# ── Step 5: Apply database schema ───────────────────────────
info "Step 5/7: Applying database schema..."
npx wrangler d1 execute toss-db --remote --file=schema.sql
ok "Database schema applied."

# ── Step 6: Set JWT secret ──────────────────────────────────
info "Step 6/7: Generating JWT secret..."
JWT_SECRET=$(openssl rand -hex 32)
echo "$JWT_SECRET" | npx wrangler secret put JWT_SECRET
ok "JWT secret set."

# ── Step 7: Deploy ──────────────────────────────────────────
info "Step 7/7: Deploying Worker..."
DEPLOY_OUTPUT=$(npx wrangler deploy 2>&1)
echo "$DEPLOY_OUTPUT"

WORKER_URL=$(echo "$DEPLOY_OUTPUT" | grep -oE 'https://[^ ]+workers\.dev' | head -1)

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Toss server deployed successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
if [ -n "${WORKER_URL:-}" ]; then
    echo -e "  Server URL:  ${CYAN}${WORKER_URL}${NC}"
    echo ""
    echo "  Next steps:"
    echo "    1. Install the CLI:    npm install -g toss-cli"
    echo "    2. Initialize:         toss init"
    echo "    3. Set server URL:     edit ~/.toss/config.yaml"
    echo "       base_url: ${WORKER_URL}"
    echo "    4. Login:              toss login --pat"
    echo "    5. Invite your team:   toss group create my-team"
    echo "                           toss group invite my-team"
else
    echo "  Could not detect Worker URL from deploy output."
    echo "  Check the Cloudflare dashboard for your Worker URL."
fi
echo ""
