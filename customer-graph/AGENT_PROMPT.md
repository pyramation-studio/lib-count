# Handoff prompt: implement customer-graph as pgpm modules + a TypeScript crawler

You are a pgpm engineer working in the `lib-count` repo, inside the folder `customer-graph/`. Read `README.md`, `PROPOSAL.md`, `intent.example.yaml` and the reference scripts in `scripts/` first.

Your job is to turn the exploratory Python into a **deterministic, re-runnable pipeline**: a Postgres schema delivered as pgpm modules, plus a TypeScript crawler that loads it.

## Context
- **Goal:** map which packages, repos, companies and developers depend on Constructive's packages (published from the `constructive-io` GitHub org and the `pyramation` npm account), on npm and GitHub. Track **current and past** users with **added/removed dates**, direct vs transitive usage, and ownership/people with **source + confidence** on every inferred claim.
- **Existing patterns to copy:**
  - lib-count's `packages/npm`, `packages/github` and `packages/stats-db`: the npm registry client, Octokit with throttling/retry, `pgsql-test`, and `update_stats.sh` style retries.
  - `constructive-io/constructive` `.agents/skills/pgpm/references/*`: `sql-conventions.md`, `pgpm-tables.md`, `module-naming.md`, `plan-format.md`, `testing.md`.
  - `constructive-io/pgpm-modules`: per-object deploy/revert/verify layout with `pgpm-verify`.
- **Data-source facts** (details in README.md):
  - npmjs.com dependents return JSON with header `x-spiferack: 1` (latest version only, 36 per page).
  - ecosyste.ms undercounts, so union it.
  - deps.dev gives counts only.
  - GitHub dependents HTML is inflated, stale and transitive, so verify against manifests and lockfiles.
  - History comes from npm packument version walks and git manifest/lockfile history.

## Hard rules
1. **Privacy.**
   - People, employer and contact data lives only in the `graph_people` schema, in a **separate database** (default `customer_graph`). It must never reach this repo, lib-count's README or badges, `stats_dev`, `packages/stats-db/src/dump.ts` output, the `lib-count-downloads` repo, or any public artifact.
   - Commit no data: no CSV/JSON/JSONL fixtures containing real names. Test fixtures must be synthetic (`example-org/example-repo`, `jdoe`).
   - Don't store commit emails.
2. **Isolation.**
   - `customer-graph/` is its own pgpm + pnpm workspace (own `pgpm.json`, `package.json`, `pnpm-workspace.yaml`).
   - Do **not** add it to lib-count's root `pgpm.json` or `pnpm-workspace.yaml`, and don't modify `packages/stats-db`, `update_stats.sh` or the badges.
3. **pgpm conventions:**
   - One change per object (`schemas/graph/schema`, `schemas/graph/tables/<t>/table`, `.../procedures/<fn>`, `.../views/<v>`), each with deploy, revert and verify plus a `pgpm.plan` entry listing its `requires`.
   - **No `CREATE OR REPLACE`.** **No `BEGIN`/`COMMIT`** in change files (pgpm wraps them).
   - `COMMENT ON` every table and every column.
   - Index every FK column.
   - Verify files use `pgpm-verify` helpers (`assert_schema`, `assert_table`, `assert_function`, `assert_view`, `assert_index`, `assert_trigger`; see `pgpm-modules/packages/verify`), and `pgpm-verify` is listed in the `.control` `requires`.
   - The `.control` name and `%project` use no scope; the npm name in `package.json` may be scoped.
4. **Determinism:**
   - Natural-key uuid v5 ids, idempotent upserts, and append-only `edge_observation`.
   - An edge gets `removed_at` **only** when a run with `status='complete'` for its target no longer observes it.
   - Every crawl is a `crawl_run` row with its `params` and the crawler's git sha.
5. **Provenance:** every inferred field (person merge, organization, employment, owner, noise classification) has `source_id`, `confidence`, and evidence text or URL. Never invent an employer. Treat GitHub `company` as self-reported (`medium`).
6. **Config:** use `@pgpmjs/env` / `pg-env`, not raw `process.env`. Tests use `pgsql-test` `getConnections()` with `beforeEach`/`afterEach` hooks, never `new pg.Pool()`.
7. **Git:** don't push to `main`, don't force-push, and don't open PRs unless the user asks.

## Phases and acceptance criteria

### Phase 0: schema
- **Build:**
  - `pgpm init workspace` in `customer-graph/`.
  - Module `packages/graph-core`: `source`, `crawl_run`, `package`, `package_download_snapshot`, `repository`, `repository_snapshot`, `package_repository`, `dependency_edge`, `edge_observation`, `target_count_snapshot`, plus procedures `observe_edge` and `close_run`.
  - Module `packages/graph-people`: `account`, `person`, `person_account`, `organization`, `repository_owner`, `employment_claim`, `package_maintainer`, `edge_commit_event`, `annotation`.
  - Seed `graph.source` rows from `intent.example.yaml` `sources`.
- **Accept when:**
  - `pgpm deploy --database customer_graph_test --createdb --yes`, then `pgpm verify`, then `pgpm revert` all succeed cleanly.
  - `pnpm test` (pgsql-test) passes. The tests cover: `observe_edge` idempotency (the same observation twice gives one edge and one observation row per run/source); `close_run` sets `removed_at` for unseen edges on a complete run and **not** on a partial one; a later re-observation clears `removed_at` and keeps `first_seen_at`.
  - Every column has a comment and every FK has an index. Add a test that queries `pg_catalog` to assert both.

### Phase 1: npm crawler (`packages/crawler`, TypeScript)
- **Build:**
  - Sources: `npm-registry` (search, packument), `npm-downloads`, `npm-web` (x-spiferack), `ecosystems`, `depsdev`.
  - Tasks: `seed-ours` (reuse lib-count's search plus `categories.ts` families), `npm-dependents`, `enrich-registry`, `npm-history` (packument version walk → `added_on`/removal events), `hop --depth 2 --top N`.
  - Plumbing: retry/backoff on 429/5xx, an on-disk raw cache under `data/cache`, and a CLI entry point (`pnpm crawl <task> [--intent intent.yaml]`).
- **Accept when:**
  - A full run against a small target list (e.g. 3 of our packages) completes and is **repeatable**: a second run produces no new edges and only new observation rows.
  - Unit tests use recorded synthetic HTTP fixtures, not live network.
  - Row counts per source are logged into `crawl_run.stats`.

### Phase 2: GitHub
- **Build:**
  - Sources: `github-dependents-html`, `github-api` (Octokit with throttling), `git-history` (blobless clone; sampled and bisected manifest/lockfile history; pickaxe fast path; GraphQL blame).
  - Tasks: `github-dependents`, `enrich-github`, `current-state` (direct/transitive/absent/gone), `who-added`, `people` (account → person resolution with `method` + `confidence`; company field → `employment_claim(medium)`).
- **Accept when:**
  - The min-stars threshold comes from the intent file.
  - A stale HTML dependent whose manifests no longer reference us ends as `absent`, with a `removed` `edge_commit_event` from git history.
  - Forks are flagged via `repository.is_fork`/`parent_full_name`.

### Phase 3: reports
- **Build:**
  - Module `packages/graph-reports` (views only): `customers_by_company`, `champions`, `new_dependents(since)`, `lost_dependents(since)`, `top_dependents`, `transitive_reach`, and a PII-free `public_badge_counts`.
  - `run.sh` runs the full pipeline and writes `data/exports/*.csv|md` (gitignored), with no git operations.
- **Accept when:**
  - The views deploy, verify and revert cleanly.
  - `public_badge_counts` exposes no column from `graph_people`; add a test asserting it via `pg_depend`/view definition.

### Phase 4 (optional)
- Extract `crawler/src/sources/*` into a standalone public CLI that outputs JSONL with no DB and no PII.

## Deliverables per phase
- Code plus tests in `customer-graph/`, and an updated `customer-graph/README.md` section "How to run".
- A short note in `PROPOSAL.md` of any schema deviations.
- Run `git grep -nE '@[a-z0-9-]+\.[a-z]{2,}'` and a review of `github.com/` links before each commit, to ensure no emails and no third-party dependents' names landed in the repo.
