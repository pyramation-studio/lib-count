# customer-graph: proposal

> **Status:** design sketch. **The SQL below has not been executed or tested** (no Postgres was available when it was written). Validate it with `pgpm deploy` plus `pgsql-test` in Phase 0. Examples are generic placeholders, not real dependents.

This proposal was adapted from an exploration of lib-count, `constructive-io/constructive` (including `.agents/skills/pgpm/references/*`) and `constructive-io/pgpm-modules`.

---

## 1. What lib-count is today

**Purpose:** count npm downloads for every package published by the `pyramation` npm account, roll them up into brands and categories (Constructive/launchql, pgpm, Hyperweb/Cosmology chain stuff, utils...), and publish a README table plus shields.io badge JSON (`badges/`, `output/badges/`). Other READMEs embed those badges.

**Shape:** pnpm + lerna monorepo that is also a **pgpm workspace** (`pgpm.json` → `packages/*`, `extensions/*`).

| package | kind | contents |
|---|---|---|
| `packages/npm` (`npm.control`, project `npm`) | pgpm module | schema `npm_count`: `npm_package(package_name PK, creation_date, last_publish_date, last_fetched_date, is_active)`, `daily_downloads(package_name, date, download_count, UNIQUE(package,date))` with a uuid v5 id derived from pkg+date, `category`, `package_category`, plus triggers: `validate_download_date` (7-day grace before creation) and `updated_at`. Also a `missing_download_dates` recursive view. One big `deploy/npm.sql` change; revert/verify are empty stubs; `sql/npm--0.0.1.sql` is the packaged extension. |
| `packages/github` (project `github`) | pgpm module | schema `github`: `organization`, `author`, `author_email`, `repository` (with fork-detection method/confidence), `daily_contribution`, `author_organization_history`, `organization_connection` (shared contributors between orgs), `contribution_summary`, and (change 2) `contributor`, `contributor_email`, `contributor_organization`. Built for *your own* orgs' contributors, not dependents. |
| `packages/stats-db` (project `stats-db`, requires `npm,github`) | pgpm module (empty plan) + the TypeScript app | `src/tasks/npm/*`: `fetch-packages.ts` discovers packages via registry search `author:/maintainer:/publisher:pyramation`, upserts them, applies the whitelist/categories from `src/config/categories.ts` (1,384 lines, hand-maintained) and the blacklist. `fetch-downloads.ts` pulls `api.npmjs.org/downloads/range` in 30-day chunks, gap-aware via `date-chunks.ts`, each chunk in its own transaction. `fix-date-offset.ts`, `stats-window.ts` (excludes npm outage days), `npm.reports.ts`, `npm.gen-readme.ts`. `src/tasks/github/*`: Octokit with throttling/retry, `fetch-all.ts` for org repos, contributors and commit-email sampling, `fork-detection.ts`, reports and exports. `dump.ts`: `pg_dump stats_dev`, gzip, optional S3 upload. DB access is `@cosmology/db-client` + `pg`; tests use `pgsql-test`. |
| `packages/stats-db-loaded` (requires `stats-db`) | pgpm module | `load.sh` downloads a full SQL insert dump from the **public** repo `constructive-io/lib-count-downloads` into `deploy/data.sql`, so a fresh DB starts with history. |

**How it runs:**
- `update_stats.sh` runs `fix:date-offset`, `fetch:packages`, `fetch:downloads` (retry on 429) and a gap check with backfill. It then regenerates the report, badges and README, then commits, pushes a branch to the fork and opens a PR against `constructive-io/lib-count`.
- `.github/workflows/get-data.do-not-run-yml` is the disabled CI version (pgpm deploy, fetch, `gh:fetch`, S3 dump).

**Things that matter for this decision:**
1. All three repos are **public**: pyramation-studio/lib-count, constructive-io/lib-count and constructive-io/lib-count-downloads. `dump.ts` dumps the **whole** `stats_dev` DB, and the "loaded" module pulls a public dump.
2. `gh:fetch` has `CLEAR_DATA_BEFORE_FETCH: true`, which runs `DELETE FROM` on the github tables, so anything else stored there gets wiped. Its org list (`hyperweb-io, interweb-inc, launchql`) is stale: no `constructive-io`.
3. Every row in `npm_count.npm_package` ends up in the totals and badges. Non-whitelisted packages fall into `misc`, which rolls up into "Utilities". Adding external dependents there would inflate the public download numbers.
4. There is no concept of dependents, third-party packages, people/employers, provenance (source/confidence) or added/removed history.
5. pgpm hygiene is light: a single monolithic change, empty revert/verify, no `pgpm-verify`. constructive's pgpm skill says: one change per object (`schemas/<s>/tables/<t>/table`), no `CREATE OR REPLACE`, no `BEGIN/COMMIT` in change files (pgpm wraps them; older pgpm-modules files still have them), `COMMENT ON` everything, index FKs, and verify with `pgpm-verify` helpers (`assert_table`, `verify_function`...).

## 2. Options considered

| | (a) dedicated pgpm workspace for the customer graph | (b1) put the tables inside lib-count's existing modules/DB | (b2) a standalone npm package/CLI (dependents crawler) first |
|---|---|---|---|
| Reuse | Copies lib-count's layout and conventions; reuses its npm/Octokit client code | Maximum: same DB, clients, pgsql-test, runner | Crawler logic only |
| Privacy | Separate (private) DB; PII never mixed with public stats | lib-count's repo, dumps and dump repo are **public**, and `dump.ts` dumps the whole DB, so PII would leak | Code can be public, but data still needs a private store |
| Risk to existing badges/README | none | High: every row in `npm_count.npm_package` counts toward totals (uncategorized → `misc` → "Utilities"), and `gh:fetch` wipes the github tables (`CLEAR_DATA_BEFORE_FETCH: true`) | none |
| History (added/removed, snapshots) | Designed in from day 1 | Needs a new schema anyway | Not its job |
| Time to first value | ~½ day: schema plus a loader for exploration output | Similar, plus untangling the risks | Longer; premature |

## 3. Recommendation

**(a): a self-contained pgpm workspace in this folder (`customer-graph/`),** with its own `pgpm.json`, `package.json` and `pnpm-workspace.yaml`. It is deliberately *not* added to lib-count's root `pgpm.json` or `pnpm-workspace.yaml`, so `stats-db` deploys, dumps and badges never touch it. It is deployed to its own database (for example `customer_graph`).

- **Code** (schema plus crawler) may live in this public repo.
- **Data** never does. Since the folder is self-contained, it can later move to a private repo as-is (an open decision).
- **Later:** extract the generic crawler (sources → JSONL, no storage, no PII) as a public package/CLI, e.g. `@constructive-io/deps-graph`.
- **Optionally** publish *aggregate, PII-free* "used by N" counts back into lib-count badges, and only with approval.

## 4. Workspace / module layout

```
customer-graph/
  pgpm.json                          { "packages": ["packages/*"] }
  package.json  pnpm-workspace.yaml  (own workspace; not part of lib-count's root workspace)
  run.sh                             full pipeline (like update_stats.sh, but no PR/push step)
  intent.example.yaml                what to track + thresholds + field provenance
  scripts/                           Python reference implementations (exploration)
  packages/
    graph-core/                      pgpm module  -> schema graph        (public-safe facts)
      graph-core.control             requires = 'plpgsql,uuid-ossp,citext,pgpm-verify'
      pgpm.plan
      deploy/schemas/graph/schema.sql
      deploy/schemas/graph/tables/<table>/table.sql
      deploy/schemas/graph/procedures/{upsert_package,observe_edge,close_run}.sql
      revert/...  verify/...         (mirror of deploy; verify uses pgpm-verify helpers)
      __tests__/graph-core.test.ts   (pgsql-test: edge first_seen/removed_at logic)
    graph-people/                    pgpm module  -> schema graph_people (PII; never exported publicly)
      requires = 'graph-core'
    graph-reports/                   pgpm module  -> schema graph_reports (views only)
      requires = 'graph-core,graph-people'
      views: customers_by_company, champions, new_dependents, lost_dependents,
             top_dependents, transitive_reach, public_badge_counts (PII-free)
    crawler/                         TS package (later extracted as a public CLI)
      src/sources/{npm-registry,npm-web,ecosystems,depsdev,github-api,github-dependents-html,git-history}.ts
      src/tasks/{seed-ours,npm-dependents,npm-history,github-dependents,current-state,
                 enrich-registry,enrich-github,who-added,hop,people,load-legacy,export}.ts
      src/db.ts                      (pg-env / @pgpmjs/env config, not raw process.env)
  data/                              gitignored: caches, exports, local annotations
```

Deploy with `pgpm deploy --database customer_graph --createdb --yes` from `customer-graph/`. Use `pgpm install @pgpm/verify` (and optionally `@pgpm/stamps`).

## 5. Proposed schema (DDL sketch, untested)

Conventions:
- uuid PKs, using uuid v5 of the natural key so reloads are idempotent (the same trick as `npm_count.set_id_from_pkg_date`).
- Every fact carries `source_id` and `confidence`.
- Observations are append-only, and "current state" is derived from them.
- In the real modules each table, procedure and view is **its own pgpm change**, and the `BEGIN`/`COMMIT` wrappers are omitted (pgpm adds them).

```sql
-- graph-core ------------------------------------------------------------
CREATE SCHEMA graph;
CREATE TYPE graph.confidence AS ENUM ('high','medium','low','unknown');

CREATE TABLE graph.source (            -- e.g. npm-web, npm-registry, ecosystems, depsdev,
  id text PRIMARY KEY,                 -- github-dependents-html, github-api, git-log-S,
  description text, base_url text      -- git-blame, lockfile, manual, web-search
);

CREATE TABLE graph.crawl_run (
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  task text NOT NULL,                  -- 'npm-dependents', 'github-dependents', ...
  source_id text REFERENCES graph.source,
  params jsonb NOT NULL DEFAULT '{}',  -- targets, depth, min_stars, offsets
  code_version text,                   -- git sha of crawler
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  status text NOT NULL DEFAULT 'running' CHECK (status IN ('running','complete','partial','failed')),
  stats jsonb
);

CREATE TABLE graph.package (
  id uuid PRIMARY KEY,                 -- uuid_v5(ecosystem||':'||name)
  ecosystem text NOT NULL DEFAULT 'npm',
  name text NOT NULL,
  is_ours boolean NOT NULL DEFAULT false,
  family text,                         -- 'constructive','hyperweb','cosmology',... (from lib-count categories)
  description text, homepage text, repository_url text,
  latest_version text, created_on date, last_publish_on date, deprecated boolean,
  first_seen_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (ecosystem, name)
);

CREATE TABLE graph.package_download_snapshot (   -- weekly point counts for ANY package
  package_id uuid REFERENCES graph.package ON DELETE CASCADE,
  period text NOT NULL,                -- 'last-week' | 'last-month'
  window_start date NOT NULL, window_end date NOT NULL,
  downloads bigint NOT NULL,
  run_id uuid REFERENCES graph.crawl_run,
  PRIMARY KEY (package_id, period, window_end)
);

CREATE TABLE graph.repository (
  id uuid PRIMARY KEY,                 -- uuid_v5('github:'||lower(full_name))
  host text NOT NULL DEFAULT 'github.com',
  full_name citext NOT NULL,           -- owner/name
  owner_login citext NOT NULL,
  github_id bigint UNIQUE,
  is_fork boolean, parent_full_name citext, archived boolean,
  description text, homepage text, pushed_at timestamptz,
  UNIQUE (host, full_name)
);
CREATE TABLE graph.repository_snapshot (           -- stars over time
  repository_id uuid REFERENCES graph.repository ON DELETE CASCADE,
  observed_on date NOT NULL, stars int, forks int, run_id uuid REFERENCES graph.crawl_run,
  PRIMARY KEY (repository_id, observed_on)
);
CREATE TABLE graph.package_repository (              -- npm pkg <-> repo (+ monorepo path)
  package_id uuid REFERENCES graph.package ON DELETE CASCADE,
  repository_id uuid REFERENCES graph.repository ON DELETE CASCADE,
  directory text, source_id text REFERENCES graph.source,
  is_upstream_of_fork boolean DEFAULT false,         -- e.g. unofficial republish of a third-party project, personal fork
  PRIMARY KEY (package_id, repository_id)
);

-- The core edge: "X depends on our package P"
CREATE TABLE graph.dependency_edge (
  id uuid PRIMARY KEY,                 -- uuid_v5(dependent_key||'->'||target||':'||manifest_path)
  dependent_package_id uuid REFERENCES graph.package,      -- exactly one of these two
  dependent_repository_id uuid REFERENCES graph.repository,
  target_package_id uuid NOT NULL REFERENCES graph.package, -- usually is_ours, or a hop-1 dependent
  hop smallint NOT NULL DEFAULT 1,     -- 1 = direct on ours, 2 = depends on a dependent
  dep_type text,                       -- prod|dev|peer|optional|transitive(lockfile)|unknown
  version_range text, manifest_path text,
  first_seen_at timestamptz NOT NULL,  -- derived from edge_observation
  last_seen_at timestamptz NOT NULL,
  removed_at timestamptz,              -- set when a COMPLETE run for this target no longer sees it
  added_on date,                       -- from git history if known (who_added)
  CHECK (num_nonnulls(dependent_package_id, dependent_repository_id) = 1)
);
CREATE TABLE graph.edge_observation (  -- append-only; one row per (edge, run, source)
  edge_id uuid REFERENCES graph.dependency_edge ON DELETE CASCADE,
  run_id uuid REFERENCES graph.crawl_run,
  source_id text REFERENCES graph.source,
  observed_at timestamptz NOT NULL DEFAULT now(),
  version_range text, dep_type text,
  PRIMARY KEY (edge_id, run_id, source_id)
);
CREATE TABLE graph.target_count_snapshot (    -- what each source claims in total (sources disagree; keep all)
  package_id uuid REFERENCES graph.package, source_id text REFERENCES graph.source,
  observed_on date, direct_count int, indirect_count int, run_id uuid REFERENCES graph.crawl_run,
  PRIMARY KEY (package_id, source_id, observed_on)
);
-- procedures: graph.observe_edge(...) upserts edge + observation, bumps last_seen_at, clears removed_at;
-- graph.close_run(run_id) marks run complete and sets removed_at on edges for that run's targets
--   whose last_seen_at < run.started_at (only for status='complete' runs, so partial crawls never delete).

-- graph-people (private) --------------------------------------------------
CREATE SCHEMA graph_people;
CREATE TABLE graph_people.account (     -- an identity on one platform
  id uuid PRIMARY KEY,                  -- uuid_v5(platform||':'||lower(login))
  platform text NOT NULL CHECK (platform IN ('github','npm','x','linkedin','web')),
  login citext NOT NULL, kind text CHECK (kind IN ('user','org','unknown')),
  display_name text, company_raw text, blog text, location text, bio text, email_public text,
  platform_id bigint, fetched_at timestamptz,
  UNIQUE (platform, login)
);
CREATE TABLE graph_people.person (id uuid PRIMARY KEY DEFAULT uuid_generate_v4(), display_name text NOT NULL, notes text);
CREATE TABLE graph_people.person_account (   -- identity resolution, e.g. npm 'jdoe-work' = github 'jdoe'
  person_id uuid REFERENCES graph_people.person ON DELETE CASCADE,
  account_id uuid REFERENCES graph_people.account ON DELETE CASCADE,
  method text NOT NULL,                 -- 'same-login','npm-repo-owner','name-match','manual'
  confidence graph.confidence NOT NULL, source_id text REFERENCES graph.source,
  PRIMARY KEY (person_id, account_id)
);
CREATE TABLE graph_people.organization (     -- a company/project (not just a GitHub org)
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  name text NOT NULL, domain citext UNIQUE,
  kind text CHECK (kind IN ('company','oss-project','affiliated','individual','noise')),
  github_account_id uuid REFERENCES graph_people.account, npm_scope text
);
CREATE TABLE graph_people.repository_owner (  -- who owns a dependent repo/package
  repository_id uuid REFERENCES graph.repository, organization_id uuid REFERENCES graph_people.organization,
  source_id text REFERENCES graph.source, confidence graph.confidence NOT NULL,
  PRIMARY KEY (repository_id, organization_id)
);
CREATE TABLE graph_people.employment_claim (  -- NEVER a bare fact: always source + evidence + confidence
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  person_id uuid NOT NULL REFERENCES graph_people.person ON DELETE CASCADE,
  organization_id uuid NOT NULL REFERENCES graph_people.organization,
  title text, evidence text NOT NULL, evidence_url text,
  source_id text NOT NULL REFERENCES graph.source, confidence graph.confidence NOT NULL,
  observed_at timestamptz NOT NULL DEFAULT now(), valid_from date, valid_to date,
  superseded_by uuid REFERENCES graph_people.employment_claim
);
CREATE TABLE graph_people.package_maintainer (
  package_id uuid REFERENCES graph.package ON DELETE CASCADE,
  account_id uuid REFERENCES graph_people.account ON DELETE CASCADE,
  role text NOT NULL DEFAULT 'maintainer',   -- maintainer|publisher|author
  first_seen_at timestamptz NOT NULL DEFAULT now(), last_seen_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (package_id, account_id, role)
);
CREATE TABLE graph_people.edge_commit_event (  -- "who added/last touched the dep line" (champions)
  edge_id uuid REFERENCES graph.dependency_edge ON DELETE CASCADE,
  event text CHECK (event IN ('added','removed','last_touched','version_bump')),
  commit_sha text, committed_on date, author_account_id uuid REFERENCES graph_people.account,
  author_name text, message text, source_id text REFERENCES graph.source,
  PRIMARY KEY (edge_id, event, commit_sha)
);
CREATE TABLE graph_people.annotation (          -- replaces annotations.py
  id uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
  entity_type text NOT NULL, entity_id uuid NOT NULL,
  key text NOT NULL, value text, source_id text REFERENCES graph.source,
  confidence graph.confidence, author text, created_at timestamptz DEFAULT now()
);
```

Also:
- Index every FK column.
- `COMMENT ON` every table and column.
- No `CREATE OR REPLACE`: to change a function, add a new change.

**Usage history:**
- **Added/removed as we observed it:** `first_seen_at` / `last_seen_at` / `removed_at` on the edge, derived from `edge_observation` across *complete* runs. Partial runs never remove anything.
- **Added/removed in the dependent's own history:** `added_on` plus `edge_commit_event`, from git history (manifest/lockfile bisection, `git log -S`, blame) and from npm packument version walks (first, last and first-without versions).
- **Popularity over time:** `package_download_snapshot` and `repository_snapshot`.

## 6. Reference scripts → ingestion tasks

Scripts live in `scripts/` and write to `$CG_DATA_DIR`.

| reference script | crawler task | writes to |
|---|---|---|
| `npm/01_list_packages.py` (registry search by maintainer) | `seed-ours` (reuse lib-count's author/maintainer/publisher search and **`categories.ts`** for `family`) | `graph.package(is_ours=true)` |
| `npm/02_downloads.py` (last-week point; bulk only for unscoped) | `enrich-registry --downloads` | `package_download_snapshot` |
| `npm/03_dependents.py` (npmjs.com `x-spiferack: 1` JSON + ecosyste.ms) | `npm-dependents` (one run per source) | `dependency_edge`, `edge_observation`, `target_count_snapshot` |
| `npm/04_enrich.py` (packument: repo, maintainers, declared deps; gh repo/user) | `enrich-registry`, then `enrich-github` | `package_repository`, `repository(+_snapshot)`, `account`, `package_maintainer`, `repository_owner` |
| `npm/05_hop2_and_depsdev.py` | `hop --depth 2 --top N`, `depsdev-counts` | edges with `hop=2`; `target_count_snapshot(source='depsdev')` |
| `npm/06_flags.py` (own-ecosystem, scope≠owner, known republishes) | SQL views over `package_repository.is_upstream_of_fork`, `repository.is_fork` | `graph_reports.top_dependents` |
| `npm/npm_history.py` (packument version walk; ecosyste.ms `latest=false`) | `npm-history` | edge `added_on`, `removed_at`; `edge_commit_event(source='npm-registry')` |
| `github/list_packages.py` (org repos → package.json names) | `seed-ours --from-github-org` | `package_repository` for ours |
| `github/scrape_dependents.py` (network/dependents HTML) | `github-dependents` | `dependency_edge(dependent_repository_id)`, source `github-dependents-html` |
| `github/enrich.py` (repo + owner profile + manifest usage) | `enrich-github` | `repository`, `account`, edge `dep_type`/`manifest_path` |
| `github/current_state.py` (default-branch manifests + lockfiles) | `current-state` | edge `dep_type` (`direct`/`transitive`), stale → `removed_at` candidates |
| `github/who_pulls.py` (lockfile parse: which package pulls ours) | part of `current-state` | `dependency_edge(dep_type='transitive')` + via-package |
| `github/git_history.py` (blobless clone, sampled + bisected manifest history) | `who-added --history` | `edge_commit_event(added/removed)`, `added_on` |
| `github/who_added.sh` (`git log -S` pickaxe) | `who-added --pickaxe` (fast path) | `edge_commit_event(event='added')` |
| `github/who_added_blame.py` (GraphQL blame on the dep line) | `who-added --blame` | `edge_commit_event(event='last_touched')` |
| `github/champions.py` | `people` (accounts → persons; company field → claim) | `person`, `person_account`, `employment_claim(confidence=medium, source=github-api)` |
| `github/build_past_users.py` | `graph_reports.lost_dependents` view | none (view) |
| `github/annotations.py` (EMPTY template) | manual edits directly in the tables | `annotation`, `employment_claim(source=manual)` |
| `github/build_outputs.py` | `graph_reports.*` + `export` | `data/exports/*` (gitignored) |

## 7. Incremental plan

1. **Phase 0:** scaffold the workspace (`pgpm init workspace` inside `customer-graph/`) and the `graph-core` + `graph-people` tables, with pgsql-test smoke tests. Add `load-legacy` to import an exploration run's CSVs from `$CG_DATA_DIR` as dated `crawl_run`s (optional baseline).
2. **Phase 1:** a deterministic npm crawler in TS with idempotent upserts via `observe_edge`/`close_run`, retry/backoff, and a raw-response cache. Tests for the removal semantics.
3. **Phase 2:** GitHub dependents, current state, git history, blame, and identity resolution with explicit `method` and `confidence`.
4. **Phase 3:** `graph_reports` views, a weekly `run.sh` that writes a private diff (new/lost dependents), and optionally the PII-free `public_badge_counts`.
5. **Phase 4 (optional):** extract `crawler/src/sources/*` into a public CLI.

## 8. Open decisions
- Keep `customer-graph/` in this public repo (code only), or move it to a private repo once data loading starts?
- Separate `customer_graph` DB on the same Postgres as `stats_dev`? (Assumed yes, with no cross-DB writes.)
- Track affiliated brands (Hyperweb/Cosmology) too, or Constructive only? `family` supports both.
- Retention and handling of personal data. The proposal stores only public-profile fields, with a cited source, and no commit emails.
- Thresholds (min stars/downloads) and cadence; see `intent.example.yaml`.
