# AGENTS.md — lib-count

## ⚠️ THROTTLE RULE — NON-NEGOTIABLE

When fetching npm download data, **always** use:

```bash
pnpm npm:fetch:downloads -- --concurrent 1 --delay 1500
```

**Do NOT change these values.** Higher concurrency or lower delay WILL result in npm 429 rate-limit errors. This is the only approved configuration.

For backfill mode (scanning all packages for gaps):

```bash
pnpm npm:fetch:downloads -- --backfill --concurrent 1 --delay 1500
```

---

## Standard Workflow

Run from `packages/stats-db/`:

```bash
# Step 1: Index packages from npm registry
pnpm npm:fetch:packages

# Step 2: Fetch download counts (ONLY approved throttle)
pnpm npm:fetch:downloads -- --concurrent 1 --delay 1500

# Step 3: Generate reports, badges, README
pnpm npm:report && pnpm npm:badges && pnpm npm:readme
```

## DB Setup (from scratch)

```bash
export PATH="$HOME/.nvm/versions/node/v22.22.0/bin:/opt/homebrew/Cellar/libpq/18.2/bin:$PATH"
eval "$(pgpm env)"
pgpm deploy --database stats_dev --createdb --yes --package npm
pgpm deploy --database stats_dev --yes --package github
pgpm deploy --database stats_dev --yes --package stats-db
psql stats_dev < ~/Constructive/lib-count-downloads/stats_dev_inserts.sql
export DATABASE_URL=postgres://postgres:password@localhost:5432/stats_dev
```

## Environment

- **Database:** `stats_dev` (pgpm Docker Postgres)
- **`.env` location:** `packages/stats-db/.env`
- **Required vars:** `DATABASE_URL`, `GITHUB_TOKEN`
