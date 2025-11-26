import { PoolClient } from "pg";

interface NpmDownloadCount {
  packageName: string;
  date: Date;
  downloadCount: number;
}

interface DailyDownload {
  date: Date;
  downloadCount: number;
}

export async function getDownloadsByPackage(
  client: PoolClient,
  packageName: string,
  startDate: Date,
  endDate: Date
): Promise<NpmDownloadCount[]> {
  const query = `
    SELECT package_name, date, download_count
    FROM npm_count.daily_downloads
    WHERE package_name = $1
    AND date BETWEEN $2 AND $3
    ORDER BY date ASC;
  `;

  const result = await client.query(query, [packageName, startDate, endDate]);

  return result.rows.map((row) => ({
    packageName: row.package_name,
    date: row.date,
    downloadCount: Number(row.download_count),
  }));
}

export async function getTotalDownloadsByPackage(
  client: PoolClient,
  packageName: string,
  startDate: Date,
  endDate: Date
): Promise<number> {
  const query = `
    SELECT SUM(download_count) as total
    FROM npm_count.daily_downloads
    WHERE package_name = $1
    AND date BETWEEN $2 AND $3;
  `;

  const result = await client.query(query, [packageName, startDate, endDate]);
  return Number(result.rows[0].total) || 0;
}

export async function getTopPackagesByDownloads(
  client: PoolClient,
  startDate: Date,
  endDate: Date,
  limit = 10
): Promise<Array<{ packageName: string; totalDownloads: number }>> {
  const query = `
    SELECT 
      package_name,
      SUM(download_count) as total_downloads
    FROM npm_count.daily_downloads
    WHERE date BETWEEN $1 AND $2
    GROUP BY package_name
    ORDER BY total_downloads DESC
    LIMIT $3;
  `;

  const result = await client.query(query, [startDate, endDate, limit]);

  return result.rows.map((row) => ({
    packageName: row.package_name,
    totalDownloads: Number(row.total_downloads),
  }));
}

export async function getDailyAverageDownloads(
  client: PoolClient,
  packageName: string,
  startDate: Date,
  endDate: Date
): Promise<number> {
  const query = `
    SELECT AVG(download_count) as avg_downloads
    FROM npm_count.daily_downloads
    WHERE package_name = $1
    AND date BETWEEN $2 AND $3;
  `;

  const result = await client.query(query, [packageName, startDate, endDate]);
  return Number(result.rows[0].avg_downloads) || 0;
}

export async function insertPackage(
  client: PoolClient,
  packageName: string,
  creationDate: Date,
  lastPublishDate: Date
): Promise<void> {
  const query = `
    INSERT INTO npm_count.npm_package (
      package_name, 
      creation_date,
      last_publish_date
    )
    VALUES ($1, $2, $3)
    ON CONFLICT (package_name) 
    DO UPDATE SET 
      creation_date = EXCLUDED.creation_date,
      last_publish_date = EXCLUDED.last_publish_date,
      updated_at = CURRENT_TIMESTAMP;
  `;

  await client.query(query, [packageName, creationDate, lastPublishDate]);
}

export async function getPackageMetadata(
  client: PoolClient,
  packageName: string
): Promise<{ packageName: string; creationDate: Date } | null> {
  const query = `
    SELECT package_name, creation_date
    FROM npm_count.npm_package
    WHERE package_name = $1;
  `;

  const result = await client.query(query, [packageName]);

  if (result.rows.length === 0) {
    return null;
  }

  return {
    packageName: result.rows[0].package_name,
    creationDate: new Date(result.rows[0].creation_date),
  };
}

export async function getPackagesCreatedBetween(
  client: PoolClient,
  startDate: Date,
  endDate: Date
): Promise<Array<{ packageName: string; creationDate: Date }>> {
  const query = `
    SELECT package_name, creation_date
    FROM npm_count.npm_package
    WHERE creation_date BETWEEN $1 AND $2
    ORDER BY creation_date DESC;
  `;

  const result = await client.query(query, [startDate, endDate]);

  return result.rows.map((row) => ({
    packageName: row.package_name,
    creationDate: new Date(row.creation_date),
  }));
}

export async function getLastDateForPackage(
  client: PoolClient,
  packageName: string
): Promise<Date | null> {
  const query = `
      SELECT MAX(date) AS last_date
      FROM npm_count.daily_downloads
      WHERE package_name = $1;
    `;

  const result = await client.query(query, [packageName]);

  // Check if a date was returned; if so, convert to a Date object.
  if (result.rows.length > 0 && result.rows[0].last_date) {
    return new Date(result.rows[0].last_date);
  }

  // Return null if no date found.
  return null;
}

export async function getPackagesWithoutDownloads(
  client: PoolClient
): Promise<Array<{ packageName: string; creationDate: Date }>> {
  const query = `
    SELECT DISTINCT p.package_name, p.creation_date
    FROM npm_count.npm_package p
    LEFT JOIN npm_count.daily_downloads d ON p.package_name = d.package_name
    WHERE d.package_name IS NULL
    AND p.is_active = true
    ORDER BY p.creation_date ASC;
  `;

  const result = await client.query(query);

  return result.rows.map((row) => ({
    packageName: row.package_name,
    creationDate: new Date(row.creation_date),
  }));
}

export async function insertDailyDownloads(
  client: PoolClient,
  packageName: string,
  downloads: DailyDownload[]
): Promise<void> {
  // Get today's date normalized to UTC midnight
  const today = new Date();
  today.setUTCHours(0, 0, 0, 0);
  const todayStr = today.toISOString().split('T')[0];

  // Separate downloads into today's and past data
  const todaysDownloads: DailyDownload[] = [];
  const pastDownloads: DailyDownload[] = [];

  for (const download of downloads) {
    const downloadDateStr = download.date.toISOString().split('T')[0];
    if (downloadDateStr === todayStr) {
      todaysDownloads.push(download);
    } else {
      pastDownloads.push(download);
    }
  }

  // For today's data: allow updates (upsert)
  const upsertQuery = `
    INSERT INTO npm_count.daily_downloads
      (package_name, date, download_count)
    VALUES ($1, $2, $3)
    ON CONFLICT (package_name, date)
    DO UPDATE SET
      download_count = EXCLUDED.download_count;
  `;

  // For past data: only insert if not exists (immutable)
  const insertOnlyQuery = `
    INSERT INTO npm_count.daily_downloads
      (package_name, date, download_count)
    VALUES ($1, $2, $3)
    ON CONFLICT (package_name, date)
    DO NOTHING;
  `;

  await Promise.all([
    ...todaysDownloads.map((download) =>
      client.query(upsertQuery, [packageName, download.date, download.downloadCount])
    ),
    ...pastDownloads.map((download) =>
      client.query(insertOnlyQuery, [packageName, download.date, download.downloadCount])
    ),
  ]);
}

export async function updateLastFetchedDate(
  client: PoolClient,
  packageName: string
): Promise<void> {
  const query = `
    UPDATE npm_count.npm_package
    SET last_fetched_date = CURRENT_DATE
    WHERE package_name = $1;
  `;

  await client.query(query, [packageName]);
}

export async function getAllPackages(
  client: PoolClient
): Promise<Array<{ packageName: string; creationDate: Date }>> {
  const query = `
    SELECT DISTINCT 
      package_name,
      creation_date
    FROM npm_count.npm_package
    ORDER BY creation_date ASC;
  `;

  const result = await client.query(query);

  return result.rows.map((row) => ({
    packageName: row.package_name,
    creationDate: new Date(row.creation_date),
  }));
}

export async function getTotalLifetimeDownloads(
  client: PoolClient,
  packageName: string
): Promise<number> {
  const query = `
    SELECT SUM(download_count) as total_downloads
    FROM npm_count.daily_downloads
    WHERE package_name = $1;
  `;

  const result = await client.query(query, [packageName]);
  return Number(result.rows[0].total_downloads) || 0;
}

export async function getExistingDownloadDates(
  client: PoolClient,
  packageName: string
): Promise<Set<string>> {
  const query = `
    SELECT date
    FROM npm_count.daily_downloads
    WHERE package_name = $1
    ORDER BY date ASC;
  `;

  const result = await client.query(query, [packageName]);

  return new Set(
    result.rows.map((row) => row.date.toISOString().split('T')[0])
  );
}

export async function getPackagesWithMissingDates(
  client: PoolClient
): Promise<Array<{ packageName: string; creationDate: Date; lastFetchedDate: Date | null }>> {
  const query = `
    SELECT
      package_name,
      creation_date,
      last_fetched_date
    FROM npm_count.npm_package
    WHERE is_active = true
    AND (
      last_fetched_date IS NULL
      OR last_fetched_date < CURRENT_DATE
    )
    ORDER BY creation_date ASC;
  `;

  const result = await client.query(query);

  return result.rows.map((row) => ({
    packageName: row.package_name,
    creationDate: new Date(row.creation_date),
    lastFetchedDate: row.last_fetched_date ? new Date(row.last_fetched_date) : null,
  }));
}
