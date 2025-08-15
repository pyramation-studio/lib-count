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
  if (downloads.length === 0) return;

  // Use bulk insert with UNNEST for better performance
  const query = `
    INSERT INTO npm_count.daily_downloads (package_name, date, download_count)
    SELECT $1, * FROM UNNEST($2::date[], $3::bigint[])
    ON CONFLICT (package_name, date) 
    DO UPDATE SET 
      download_count = EXCLUDED.download_count;
  `;

  const dates = downloads.map(d => d.date);
  const counts = downloads.map(d => d.downloadCount);

  await client.query(query, [packageName, dates, counts]);
}

export async function insertDailyDownloadsBulk(
  client: PoolClient,
  packageDownloads: Array<{ packageName: string; downloads: DailyDownload[] }>
): Promise<void> {
  if (packageDownloads.length === 0) return;

  // Flatten all downloads into single arrays for maximum efficiency
  const packageNames: string[] = [];
  const dates: Date[] = [];
  const counts: number[] = [];

  packageDownloads.forEach(({ packageName, downloads }) => {
    downloads.forEach(download => {
      packageNames.push(packageName);
      dates.push(download.date);
      counts.push(download.downloadCount);
    });
  });

  if (packageNames.length === 0) return;

  const query = `
    INSERT INTO npm_count.daily_downloads (package_name, date, download_count)
    SELECT * FROM UNNEST($1::text[], $2::date[], $3::bigint[])
    ON CONFLICT (package_name, date) 
    DO UPDATE SET 
      download_count = EXCLUDED.download_count;
  `;

  await client.query(query, [packageNames, dates, counts]);
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

export async function updateLastFetchedDateBulk(
  client: PoolClient,
  packageNames: string[]
): Promise<void> {
  if (packageNames.length === 0) return;

  const query = `
    UPDATE npm_count.npm_package
    SET last_fetched_date = CURRENT_DATE
    WHERE package_name = ANY($1);
  `;

  await client.query(query, [packageNames]);
}

export async function getAllPackages(
  client: PoolClient
): Promise<Array<{ packageName: string; creationDate: Date }>> {
  const query = `
    SELECT DISTINCT
      package_name,
      creation_date
    FROM npm_count.npm_package
    WHERE is_active = true
    ORDER BY package_name;
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

export async function getPackagesNeedingDownloadUpdate(
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
      OR last_fetched_date < CURRENT_DATE - INTERVAL '1 day'
    )
    ORDER BY 
      CASE WHEN last_fetched_date IS NULL THEN 0 ELSE 1 END,
      last_fetched_date ASC NULLS FIRST,
      creation_date ASC;
  `;

  const result = await client.query(query);

  return result.rows.map((row) => ({
    packageName: row.package_name,
    creationDate: new Date(row.creation_date),
    lastFetchedDate: row.last_fetched_date ? new Date(row.last_fetched_date) : null,
  }));
}

export async function getMissingDateRanges(
  client: PoolClient,
  packageName: string,
  creationDate: Date
): Promise<Array<{ start: Date; end: Date }>> {
  // More efficient approach: use the existing missing_download_dates view
  const query = `
    WITH missing_dates_ordered AS (
      SELECT missing_date
      FROM npm_count.missing_download_dates
      WHERE package_name = $1
      AND missing_date >= $2::date
      AND missing_date <= CURRENT_DATE
      ORDER BY missing_date
    ),
    grouped_ranges AS (
      SELECT 
        missing_date,
        missing_date - (ROW_NUMBER() OVER (ORDER BY missing_date))::integer * interval '1 day' as group_id
      FROM missing_dates_ordered
    )
    SELECT 
      MIN(missing_date) as start_date,
      MAX(missing_date) as end_date
    FROM grouped_ranges
    GROUP BY group_id
    HAVING COUNT(*) > 0
    ORDER BY MIN(missing_date);
  `;

  const result = await client.query(query, [packageName, creationDate]);

  return result.rows.map((row) => ({
    start: new Date(row.start_date),
    end: new Date(row.end_date),
  }));
}
