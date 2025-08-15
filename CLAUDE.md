# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is the Hyperweb lib-count repository - a monorepo that tracks and reports download statistics for JavaScript packages in the Interchain/Cosmos ecosystem. It generates badges, reports, and README files with download statistics for various projects under the Hyperweb umbrella (formerly Cosmology).

## Development Commands

### Building and Development
- `yarn build` - Build all packages using Lerna
- `yarn build:dev` - Build all packages in development mode with declaration maps
- `yarn clean` - Clean all package dist directories
- `yarn lint` - Run ESLint across all packages
- `yarn symlink` - Create symlinks between workspace packages

### Database Operations (stats-db package)
- `make up` - Start PostgreSQL database with Docker Compose  
- `make down` - Stop and remove database containers
- `make ssh` - SSH into the PostgreSQL container

### NPM Statistics Tasks (stats-db package)
- `npm run npm:fetch:packages` - Fetch package information from NPM registry
- `npm run npm:fetch:downloads` - Fetch download statistics from NPM (optimized with incremental updates)
- `npm run npm:report` - Generate download reports 
- `npm run npm:badges` - Generate JSON badge files for GitHub
- `npm run npm:readme` - Generate README files with statistics

### GitHub Statistics Tasks (stats-db package)
- `npm run gh:fetch` - Fetch GitHub repository information
- `npm run gh:report` - Generate GitHub reports
- `npm run gh:export` - Export GitHub data

### Testing
- `npm run test` - Run Jest tests (client package)
- `npm run test` - Run Vitest tests (stats-db package) 
- `npm run test:watch` - Run tests in watch mode

## Architecture

### Monorepo Structure
This is a Lerna-managed monorepo with two main packages:
- `packages/client/` - Database client library (@cosmology/db-client)
- `packages/stats-db/` - Statistics collection and reporting (@hyperweb-io/stats-db)

### Key Technologies
- **Lerna** for monorepo management with independent versioning
- **TypeScript** for type safety across packages
- **tsx** for fast TypeScript execution (replaced ts-node for better performance)
- **PostgreSQL** (via Docker) for data storage with optimized bulk operations
- **Jest/Vitest** for testing
- **ESLint + Prettier** for code quality

### Database Schema
The system tracks:
- NPM package download statistics over time
- GitHub repository metadata and statistics  
- Package categorization (Web2, Web3, Utilities, etc.)
- Badge generation for displaying statistics

### Data Flow
1. Fetch package metadata from NPM registry
2. Collect download statistics over time periods
3. Store data in PostgreSQL database
4. Generate reports, badges, and README content
5. Output statistics to `badges/` and `output/` directories

## Important Files
- `package.json` - Root workspace configuration and scripts
- `lerna.json` - Lerna monorepo configuration
- `docker-compose.yml` - PostgreSQL database setup
- `packages/stats-db/src/tasks/` - Main data collection and reporting logic
- `badges/` and `output/` - Generated statistics files

## Database Connection
Default development database URL: `postgres://postgres:password@localhost:5432/example_db`

The database is containerized and managed via Docker Compose.