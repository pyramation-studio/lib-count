# customer-graph (scaffold)

**Status:** scaffold and reference scripts only. There is **no data in this folder, and there must never be.** See [`PROPOSAL.md`](./PROPOSAL.md) for the design and [`AGENT_PROMPT.md`](./AGENT_PROMPT.md) for the implementation handoff.

## Goal

Build a deterministic, re-runnable map of **who uses Constructive's software**: the companies, people and developers whose packages or repos depend on packages published from the `constructive-io` GitHub org (and Dan's npm account), covering:

- **direct dependents** on npm (packages whose manifest declares one of ours) and on GitHub (repos whose manifests or lockfiles reference one of ours);
- **transitive reach**, with a bounded second hop: who depends on our dependents;
- **current and past users**, with *added* and *removed* dates reconstructed from history, so churn and adoption can be tracked over time;
- **ownership and people**: the owning org or company, maintainers, the developer who added the dependency, and their self-reported employer. Every employer claim carries a **source and confidence** and is never invented.

The output is meant to feed a Postgres database built as pgpm modules, with snapshots per crawl run, so new and lost dependents can be diffed week to week.

## Privacy rule (non-negotiable)

People, employer and contact data (`graph_people.*`) is **private**:

- It must never be written into this repo, the lib-count README or badges, `stats_dev` dumps (`packages/stats-db/src/dump.ts`), `lib-count-downloads`, or any public artifact.
- Use a separate database (for example `customer_graph`) and keep exports under a gitignored `data/` directory.
- Only aggregate, PII-free counts (for example "used by N packages") may ever be published, and only with explicit approval.

## What was explored so far (methods and data-source findings)

The exploration produced throwaway CSVs; none are included here. These are the lessons about the **data sources**:

### npm
- **Our package inventory:** registry search `https://registry.npmjs.org/-/v1/search?text=maintainer:<user>&size=250&from=N` pages through everything a maintainer publishes. lib-count already does this with `author:`, `maintainer:` and `publisher:`. Classifying "ours vs affiliated" works best from lib-count's `categories.ts`, not from regexes.
- **Downloads:** `https://api.npmjs.org/downloads/point/last-week/<pkg>`. The bulk form (`/point/last-week/a,b,c`, up to about 100 names) only works for **unscoped** packages; scoped ones need one call each. Watch for 429s.
- **Dependents, the authoritative source:**
  - `npmjs.com` dependents pages return 403 as HTML to scripts, but the same URLs return **JSON** when sent the header **`x-spiferack: 1`**.
  - `GET https://www.npmjs.com/package/<pkg>` returns `dependents.dependentsCount`.
  - `GET https://www.npmjs.com/browse/depended/<pkg>?offset=N` returns 36 packages per page, with `hasNext`, maintainers and descriptions.
  - This is undocumented, so treat it as fragile, with backoff and caching.
- **npm dependents reflect the latest version only.** A package appears only if its *current latest* manifest declares the dependency. Past users vanish, and bundled or vendored copies and unpublished apps never show up.
- **ecosyste.ms** (`packages.ecosyste.ms/api/v1/registries/npmjs.org/packages/<pkg>/dependent_packages`): useful metadata (repo URL, maintainers, owner record) and a `latest=false` mode for any-version dependents. However, it **undercounts substantially** compared with npmjs.com, so union the two and never rely on it alone.
- **deps.dev** (`api.deps.dev/v3alpha/systems/npm/packages/<pkg>/versions/<v>:dependents`): returns only **counts** (`directDependentCount`, `indirectDependentCount`), no names. Good for a "reach" metric and as a cross-check; its numbers differ from both sources above.
- **History on npm:** the full **packument** (`https://registry.npmjs.org/<pkg>`) lists every version with its manifest plus a `time` map. Walking versions gives the first version that declared our dependency, the last version that did, and the first version without it. That yields *added* and *removed* dates for packages that dropped us.
- **The external dependents' combined downloads are small compared with ours.** Most real usage comes through apps that are never published to npm, which is why the GitHub side matters.

### GitHub
- **"Used by" / network dependents pages** (`github.com/<org>/<repo>/network/dependents?dependent_type=REPOSITORY|PACKAGE&package_id=...`):
  - HTML only (no API), paginated by `dependents_after`, and rate-limited.
  - Fuzzy in several ways: they **inflate** counts with forks, clones, tutorial copies and test fixtures, they are **stale** (repos that removed us long ago still appear), and they include **transitive** users that only show up via a lockfile.
- **Verify the current state** by reading each dependent's default-branch `package.json` files (direct) and lockfiles (`package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`, `bun.lock`; transitive). Classify each as `direct`, `transitive`, `absent` (stale), `gone`, or `no-js-manifest`.
- **Fork/clone noise:** check `repo.fork`/`parent` and dedupe identical starter-template clones. Stars on npm-linked repos can belong to an **upstream** project when a package is an unofficial republish or a personal fork. Flag cases where the npm scope differs from the repo owner.
- **History via git:**
  - A blobless clone (`git clone --filter=blob:none --no-checkout`) gives local commits and trees.
  - `git log` on manifest and lockfile paths, sampled and then bisected, reconstructs when our packages appeared and disappeared, and who committed it.
  - `git log -S'"pkg-name"'` (pickaxe) is a cheaper first-add finder.
  - GraphQL `blame` on the dependency line gives who last touched it.
- **People:** GitHub user `company`, `blog` and `bio` fields are **self-reported**. Org-owned repos give high-confidence ownership. Matching npm usernames to GitHub logins by name is **unverified** unless the npm package's repo is owned by that login.

## Layout

```
customer-graph/
  README.md               this file
  PROPOSAL.md             schema sketch, module layout, script → ingestion mapping, phases, open decisions
  intent.example.yaml     machine-readable intent: what to track, thresholds, sources, cadence, field provenance
  AGENT_PROMPT.md         handoff prompt for the pgpm engineer agent
  .gitignore              blocks data/cache/csv/json/jsonl/log/html
  scripts/
    _common.py            CG_DATA_DIR / CG_GITHUB_ORG / CG_NPM_MAINTAINERS / CG_OWN_ORGS / CG_CLONE_DIR
    npm/                  01..06 pipeline + npm_history.py (packument version history)
    github/               repo inventory, dependents scraper, enrichment, current-state check,
                          git-history add/remove reconstruction, blame, past users, outputs
                          annotations.py = EMPTY TEMPLATE (real notes go in $CG_DATA_DIR/annotations_local.py)
```

### Running the reference scripts (exploration only)

```bash
export CG_DATA_DIR=$PWD/data          # gitignored; every output lands here
python3 scripts/npm/01_list_packages.py
python3 scripts/npm/02_downloads.py
python3 scripts/npm/03_dependents.py   # slow: ~15 min for ~550 packages
python3 scripts/npm/04_enrich.py       # needs `gh` authenticated
python3 scripts/npm/05_hop2_and_depsdev.py
python3 scripts/npm/06_flags.py
python3 scripts/npm/npm_history.py     # added/removed via packument versions
# GitHub side (needs repos.tsv; see the comment in list_packages.py)
python3 scripts/github/list_packages.py
python3 scripts/github/scrape_dependents.py <repo> [<repo> ...]
MIN_STARS=10 python3 scripts/github/enrich.py
python3 scripts/github/current_state.py
python3 scripts/github/git_history.py owner/repo ...
```

These scripts are **reference implementations** of the algorithms: quick, single-threaded-ish Python with file caches and CSV hand-offs between steps. The target is the TypeScript crawler plus pgpm schema described in `PROPOSAL.md`.
