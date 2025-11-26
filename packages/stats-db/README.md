## Database Schema Management

### Prerequisites

Before deploying the database, ensure you have the required tools installed:

- **Node.js 20+** - Required for pgpm
- **PostgreSQL** - Running locally or via Docker
- **pgpm** - PostgreSQL Package Manager

Install pgpm globally:

```bash
npm install -g pgpm
```

### Start PostgreSQL (Docker)

If using Docker, start PostgreSQL with pgpm:

```bash
pgpm docker start
```

### Set Environment Variables

Configure your PostgreSQL connection using pgpm:

```bash
eval "$(pgpm env)"
```

This automatically sets:
- `PGHOST=localhost`
- `PGPORT=5432`
- `PGUSER=postgres`
- `PGPASSWORD=password`
- `PGDATABASE=postgres`

> **Tip:** Add `eval "$(pgpm env)"` to your shell config (`~/.bashrc`, `~/.zshrc`, etc.) to automatically set these variables in new terminal sessions.

Alternatively, set them manually:

```bash
export PGHOST=localhost
export PGPORT=5432
export PGUSER=postgres
export PGPASSWORD=password
export PGDATABASE=postgres
```

### Bootstrap Database Users

Create database users for testing and development (run once):

```bash
pgpm admin-users bootstrap --yes
```

This creates `anonymous`, `authenticated`, and `administrator` roles.

### Deploy the Database Module

Deploy the stats-db module to create the database schemas (npm and github):

```bash
# Create the database and deploy the module
pgpm deploy --database stats_dev --createdb --yes

# Or deploy to an existing database
pgpm deploy --database stats_dev --yes
```

Now export `DATABASE_URL`:

```sh
export DATABASE_URL=postgres://postgres:password@localhost:5432/stats_dev
```

### Running Commands

- **Fetch Packages**: Fetch package data from npm.

  ```sh
  pnpm npm:fetch:packages
  ```

- **Fetch Downloads**: Fetch download statistics.

  **Default (50 concurrent, 200ms delay):**
  ```sh
  npm run npm:fetch:downloads
  ```

  **Conservative (avoid 429 errors):**
  ```sh
  npm run npm:fetch:downloads -- --concurrent 1 --delay 1500
  # Or using short flags: -c 1 -d 1500
  ```

  **Aggressive (if rate limits improve):**
  ```sh
  npm run npm:fetch:downloads -- --concurrent 100 --delay 100
  ```

  **Backfill mode (scan for gaps in historical data):**
  ```sh
  npm run npm:fetch:downloads -- --backfill --concurrent 1 --delay 1500
  # Or using short flag: -b
  ```

  #### Command Options

  | Option | Short | Description |
  |--------|-------|-------------|
  | `--concurrent` | `-c` | Number of concurrent package downloads (default: 50) |
  | `--delay` | `-d` | Delay between requests in milliseconds (default: 200) |
  | `--chunk-size` | `-s` | Number of days per chunk (default: 30) |
  | `--backfill` | `-b` | Force scan ALL active packages for gaps |

  #### Understanding Fetch Modes

  **Normal mode** (default): Only processes packages where `last_fetched_date < TODAY`. This is efficient for daily updates but may miss gaps if a previous fetch was interrupted.

  **Backfill mode** (`--backfill`): Scans ALL active packages regardless of `last_fetched_date`. For each package, it:
  1. Retrieves all existing download dates from the database
  2. Compares against the expected date range (creation date → today)
  3. Identifies and fetches only the missing dates (gaps)
  4. Updates `last_fetched_date` after successful completion

  Use backfill mode when:
  - You suspect there are gaps in historical data
  - A previous fetch was interrupted by rate limiting (429 errors)
  - You want to verify data completeness for all packages


- **Generate Report**: Generate a report based on the fetched data.

  ```sh
  pnpm npm:report
  ```

- **Generate Badges**: Generate badges for npm packages.

  ```sh
  pnpm npm:badges
  ```

- **Generate README**: Generate README files for npm packages.

  ```sh
  pnpm npm:readme
  ```

- **Database Dump**: Create a dump of the current database state.

  ```sh
  pnpm db:dump
  ```

### Initial Setup Order

To index from scratch, follow these steps in order:

1. Deploy the database module (if not already deployed):

   ```sh
   pgpm deploy --database stats_dev --createdb --yes
   ```

2. Fetch and index the data:

   ```sh
   pnpm npm:fetch:packages && pnpm npm:fetch:downloads
   ```

3. Run reports/badges generation scripts:

   ```sh
   pnpm npm:report && pnpm npm:badges && pnpm npm:readme
   ```