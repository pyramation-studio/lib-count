# data-loaded

Database dump package containing data exports for deployment.

# Wget this 

wget https://raw.githubusercontent.com/hyperweb-io/lib-count-downloads/refs/heads/main/stats_dev_inserts.sql




## Exporting Data

To create a new data dump from the database:

```sh
pg_dump \
  --data-only \
  --inserts \
  --exclude-schema=pgpm_migrate \
  stats_dev > dump.sql
```

## Processing the Dump

1. Remove `SET` statements at the top of `dump.sql`
2. Overwrite `deploy/data.sql` with the cleaned dump file

NOTE: Don't actually commit this thought! Committing the dumped sql can make this very, very large.