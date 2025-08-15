import { Database } from "@cosmology/db-client";
import { PoolClient } from "pg";
import { NPMApiClient } from "../../npm-client";
import {
  getAllPackages,
  insertDailyDownloadsBulk,
  updateLastFetchedDateBulk,
  getPackagesNeedingDownloadUpdate,
  getMissingDateRanges,
} from "./npm.queries";
import { delay } from "../../utils";

const npmClient = new NPMApiClient();

const CONCURRENT_TASKS = 200; // Number of concurrent downloads
const RATE_LIMIT_DELAY = 50; // ms between requests
const CHUNK_SIZE = 365; // days per chunk (as per documented algorithm)
const DB_BATCH_SIZE = 50; // Number of packages to process in single DB transaction


interface DateRange {
  start: Date;
  end: Date;
}

interface PackageInfo {
  packageName: string;
  creationDate: Date;
  lastFetchedDate?: Date | null;
}

interface PackageDownloadData {
  packageName: string;
  downloads: Array<{ date: Date; downloadCount: number }>;
  success: boolean;
  error?: string;
}

function normalizeDate(date: Date): Date {
  const normalized = new Date(date);
  normalized.setUTCHours(0, 0, 0, 0);
  return normalized;
}

function getDateChunks(startDate: Date, endDate: Date): DateRange[] {
  const chunks: DateRange[] = [];
  let currentStart = normalizeDate(startDate);
  const finalEndDate = normalizeDate(
    new Date(Math.min(endDate.getTime(), new Date().getTime()))
  );

  while (currentStart < finalEndDate) {
    // Create a new chunk with proper 365-day boundaries
    const chunkEnd = new Date(currentStart);
    chunkEnd.setUTCDate(chunkEnd.getUTCDate() + CHUNK_SIZE - 1);

    // Ensure we don't go past the final end date
    const actualEnd = chunkEnd > finalEndDate ? finalEndDate : chunkEnd;

    // Only add chunk if there's at least one day to process
    if (currentStart <= actualEnd) {
      chunks.push({
        start: new Date(currentStart),
        end: new Date(actualEnd),
      });
    }

    // Move to next chunk (start day after current chunk ends)
    currentStart = new Date(actualEnd);
    currentStart.setUTCDate(currentStart.getUTCDate() + 1);

    // Prevent infinite loop
    if (currentStart > finalEndDate) {
      break;
    }
  }

  return chunks;
}

function formatDateRange(range: DateRange): string {
  const start = range.start.toISOString().split("T")[0];
  const end = range.end.toISOString().split("T")[0];
  const days =
    Math.floor(
      (range.end.getTime() - range.start.getTime()) / (1000 * 60 * 60 * 24)
    ) + 1;
  return `${start} to ${end} (${days} days)`;
}


async function fetchPackageDownloadData(
  packageName: string,
  creationDate: Date,
  dateRanges: Array<{ start: Date; end: Date }>,
  current: number,
  total: number
): Promise<PackageDownloadData> {
  try {
    const allDownloads: Array<{ date: Date; downloadCount: number }> = [];
    let chunkIndex = 0;
    const totalChunks = dateRanges.reduce((sum, range) => 
      sum + getDateChunks(range.start, range.end).length, 0
    );

    for (const dateRange of dateRanges) {
      const chunks = getDateChunks(dateRange.start, dateRange.end);
      
      for (const chunk of chunks) {
        chunkIndex++;
        await delay(RATE_LIMIT_DELAY);
        
        const dateRangeStr = formatDateRange(chunk);
        console.log(
          `[${current}/${total}] Fetching chunk ${chunkIndex}/${totalChunks} for ${packageName}: ${dateRangeStr}`
        );

        const downloadData = await npmClient.download({
          startDate: [
            chunk.start.getUTCFullYear(),
            chunk.start.getUTCMonth() + 1,
            chunk.start.getUTCDate(),
          ],
          endDate: [
            chunk.end.getUTCFullYear(),
            chunk.end.getUTCMonth() + 1,
            chunk.end.getUTCDate(),
          ],
          packageName,
        });

        if (downloadData.downloads && downloadData.downloads.length > 0) {
          const normalizedDownloads = downloadData.downloads.map((d) => ({
            date: normalizeDate(new Date(d.day)),
            downloadCount: d.downloads,
          }));
          allDownloads.push(...normalizedDownloads);
        }
      }
    }

    console.log(
      `[${current}/${total}] ✅ Fetched ${allDownloads.length} download records for ${packageName}`
    );

    return {
      packageName,
      downloads: allDownloads,
      success: true
    };
  } catch (error) {
    return {
      packageName,
      downloads: [],
      success: false,
      error: error instanceof Error ? error.message : String(error)
    };
  }
}

async function processPackageDownloads(
  db: Database,
  packageName: string,
  creationDate: Date,
  lastFetchedDate: Date | null,
  current: number,
  total: number,
  isIncremental: boolean = true
): Promise<PackageDownloadData> {
  // Get missing date ranges without database transaction
  let dateRanges: Array<{ start: Date; end: Date }> = [];
  
  await db.withTransaction(async (dbClient: PoolClient) => {
    if (isIncremental) {
      dateRanges = await getMissingDateRanges(dbClient, packageName, creationDate);
    } else {
      const today = new Date();
      dateRanges = [{ start: creationDate, end: today }];
    }
  });

  if (dateRanges.length === 0) {
    console.log(`[${current}/${total}] ⏭ ${packageName} - no missing data, skipping`);
    return {
      packageName,
      downloads: [],
      success: true
    };
  }

  // Fetch data without holding database transaction
  return await fetchPackageDownloadData(packageName, creationDate, dateRanges, current, total);
}

async function processBatch(
  db: Database,
  packages: Array<PackageInfo>,
  startIndex: number,
  total: number,
  isIncremental: boolean = true
): Promise<void> {
  console.log(`\n🚀 Starting batch of ${packages.length} packages...`);
  
  // Phase 1: Fetch all download data concurrently (no DB transactions)
  const downloadResults = await Promise.allSettled(
    packages.map((pkg, index) =>
      (async () => {
        await delay(index * RATE_LIMIT_DELAY); // Stagger the requests
        return processPackageDownloads(
          db,
          pkg.packageName,
          pkg.creationDate,
          pkg.lastFetchedDate || null,
          startIndex + index + 1,
          total,
          isIncremental
        );
      })()
    )
  );

  // Phase 2: Process results and batch successful data into database
  const successfulData: PackageDownloadData[] = [];
  const failedPackages: string[] = [];

  downloadResults.forEach((result, index) => {
    if (result.status === 'fulfilled') {
      if (result.value.success) {
        successfulData.push(result.value);
      } else {
        failedPackages.push(`${result.value.packageName}: ${result.value.error}`);
      }
    } else {
      failedPackages.push(`${packages[index].packageName}: ${result.reason}`);
    }
  });

  // Phase 3: Bulk insert all successful data in a single transaction
  if (successfulData.length > 0) {
    console.log(`\n💾 Bulk inserting data for ${successfulData.length} packages...`);
    
    try {
      await db.withTransaction(async (dbClient: PoolClient) => {
        // Filter packages that have actual download data
        const packagesWithData = successfulData.filter(p => p.downloads.length > 0);
        const packagesWithoutData = successfulData.filter(p => p.downloads.length === 0);
        
        if (packagesWithData.length > 0) {
          // Bulk insert all download data
          await insertDailyDownloadsBulk(dbClient, packagesWithData);
          
          // Bulk update last_fetched_date for packages with data
          await updateLastFetchedDateBulk(
            dbClient, 
            packagesWithData.map(p => p.packageName)
          );
          
          console.log(`✅ Bulk inserted downloads for ${packagesWithData.length} packages`);
        }
        
        if (packagesWithoutData.length > 0) {
          // Still update last_fetched_date for packages without downloads
          await updateLastFetchedDateBulk(
            dbClient, 
            packagesWithoutData.map(p => p.packageName)
          );
          
          console.log(`✅ Updated timestamps for ${packagesWithoutData.length} packages (no new downloads)`);
        }
      });
    } catch (error) {
      console.error(`❌ Bulk database operation failed:`, error);
      throw error;
    }
  }

  // Phase 4: Report results
  if (failedPackages.length > 0) {
    console.error(`\n❌ ${failedPackages.length} package(s) failed in this batch:`);
    failedPackages.forEach((failure) => {
      console.error(`  - ${failure}`);
    });
  }

  console.log(`\n📊 Batch Summary:`);
  console.log(`  ✅ Successful: ${successfulData.length}`);
  console.log(`  ❌ Failed: ${failedPackages.length}`);
  console.log(`  💾 Total downloads inserted: ${successfulData.reduce((sum, p) => sum + p.downloads.length, 0).toLocaleString()}`);
}

async function run(shouldResetDb: boolean = false): Promise<void> {
  const db = new Database();
  const scriptStartTime = Date.now();

  try {
    // Get packages based on mode - this can be outside transaction
    let packages: PackageInfo[] = [];
    let mode: string;

    await db.withTransaction(async (dbClient: PoolClient) => {
      if (shouldResetDb) {
        // Full reset mode - get all packages
        const allPackages = await getAllPackages(dbClient);
        packages = allPackages.map(pkg => ({
          packageName: pkg.packageName,
          creationDate: pkg.creationDate,
          lastFetchedDate: null
        }));
        mode = "FULL RESET";
      } else {
        // Intelligent incremental mode - get packages needing updates
        packages = await getPackagesNeedingDownloadUpdate(dbClient);
        mode = "INCREMENTAL";
      }
    });

    const totalPackages = packages.length;
    if (totalPackages === 0) {
      console.log("✅ No packages need updating!");
      return;
    }

    console.log(
      `Found ${totalPackages} package${
        totalPackages === 1 ? "" : "s"
      } to process with ${CONCURRENT_TASKS} concurrent tasks (${mode} mode)`
    );

    // Log package status breakdown
    const newPackages = packages.filter(p => !p.lastFetchedDate).length;
    const stalePackages = packages.filter(p => p.lastFetchedDate).length;
    if (mode === "INCREMENTAL") {
      console.log(
        `\nPackage breakdown:\n` +
        `  - New packages (no downloads): ${newPackages}\n` +
        `  - Stale packages (>1 day old): ${stalePackages}`
      );
    }

    let successCount = 0;
    let failureCount = 0;

    // Process packages in optimized batches (use smaller DB batch size for better transaction management)
    const effectiveBatchSize = Math.min(CONCURRENT_TASKS, DB_BATCH_SIZE);
    
    for (let i = 0; i < packages.length; i += effectiveBatchSize) {
      const batch = packages.slice(i, i + effectiveBatchSize);
      const batchNum = Math.floor(i / effectiveBatchSize) + 1;
      const totalBatches = Math.ceil(packages.length / effectiveBatchSize);
      
      console.log(
        `\n📦 Processing batch ${batchNum}/${totalBatches} (${batch.length} packages)...`
      );

      try {
        await processBatch(db, batch, i, totalPackages, !shouldResetDb);
        successCount += batch.length;
        
        // Add small delay between batches to prevent overwhelming the database
        if (i + effectiveBatchSize < packages.length) {
          await delay(1000);
        }
      } catch (error) {
        failureCount += batch.length;
        console.error(`❌ Batch ${batchNum} processing error:`, error);
        
        // Continue with next batch even if current fails
        continue;
      }
    }

    const duration = ((Date.now() - scriptStartTime) / 1000).toFixed(2);
    console.log(
      `\n${mode} processing completed in ${duration} seconds!\n` +
        `Successful packages: ${successCount}\n` +
        `Failed packages: ${failureCount}`
    );
  } catch (error) {
    const duration = ((Date.now() - scriptStartTime) / 1000).toFixed(2);
    console.error(`Script error after ${duration} seconds:`, error);
    throw error;
  }
}

type FetchDownloadsOptions = {
  resetDb?: boolean;
};

export function execute(options: FetchDownloadsOptions = {}): Promise<void> {
  return run(options.resetDb ?? false)
    .then(() => {
      console.log(`Script completed successfully!`);
      process.exit(0);
    })
    .catch((error) => {
      console.error(`Script failed:`, error);
      process.exit(1);
    });
}
