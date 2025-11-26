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

# GitHub Analytics

## **Project Overview**

A TypeScript-based tool for collecting GitHub ecosystem data to map contributor networks and organizational relationships within the Cosmos blockchain ecosystem.

## **Data Collection Requirements**

### **1. Repository Collection**

- **Target Organizations**: `hyperweb-io` and `launchql`
- **Repository Filter**: Collect only non-fork repositories from each organization
- **Repository Data**:
  - Repository ID, name, and full name
  - HTML URL and privacy status
  - Fork status (to enable filtering)

### **2. Contributor Collection**

- **Scope**: All contributors to all non-fork repositories collected in step 1
- **Contributor Data**:
  - GitHub username (login)
  - User ID
  - Contribution count per repository
  - Total contributions across all repositories

### **3. Organization Network Discovery**

- **Scope**: All public organizations that any contributor (from step 2) belongs to
- **Organization Data**:
  - Organization login/name
  - Organization API URL
  - Unique organization list (deduplicated across all contributors)

### **Data Collection Flow**

1. Fetch all repositories from `hyperweb-io` and `launchql` organizations
2. Filter out forked repositories, keeping only original repositories
3. For each non-fork repository, fetch complete contributor list
4. For each unique contributor discovered, fetch their public organization memberships
5. Aggregate and deduplicate all discovered organizations

### **Output Requirements**

- **Non-fork repositories**: Organized by parent organization
- **Contributor profiles**: Including cross-repository contribution mapping
- **Organization network**: Complete deduplicated list of all public organizations discovered through contributor analysis

This data collection strategy enables comprehensive ecosystem analysis by mapping the full network of organizations connected through shared contributors in the target GitHub organizations.
