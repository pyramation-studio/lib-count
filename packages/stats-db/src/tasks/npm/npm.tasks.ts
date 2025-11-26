import { execute as fetchPackages } from "./fetch-packages";
import { execute as fetchDownloads } from "./fetch-downloads";

import { generateReport, generateAndWriteBadges } from "./npm.reports";
import { generateAndWriteReadme } from "./npm.gen-readme";
import * as fs from "fs";
import * as path from "path";

interface CommandOptions {
  concurrentTasks?: number;
  rateLimitDelay?: number;
  chunkSize?: number;
}

function parseCommandOptions(args: string[]): CommandOptions {
  const options: CommandOptions = {};

  for (let i = 0; i < args.length; i++) {
    const arg = args[i];

    if (arg === '--concurrent' || arg === '-c') {
      options.concurrentTasks = parseInt(args[++i], 10);
    } else if (arg === '--delay' || arg === '-d') {
      options.rateLimitDelay = parseInt(args[++i], 10);
    } else if (arg === '--chunk-size' || arg === '-s') {
      options.chunkSize = parseInt(args[++i], 10);
    }
  }

  return options;
}

async function runCommand(command: string, options: CommandOptions = {}): Promise<void> {
  console.log(`Executing NPM task: ${command}`);

  switch (command) {
    case "fetch:packages":
      await fetchPackages();
      break;

    case "fetch:downloads":
      await fetchDownloads({
        resetDb: false,
        ...options
      });
      break;

    case "generate:report": {
      const report = await generateReport();
      const reportPath = path.join(__dirname, "../../../exports/npm-report.md");
      fs.mkdirSync(path.dirname(reportPath), { recursive: true });
      fs.writeFileSync(reportPath, report);
      console.log(`Report generated at: ${reportPath}`);
      break;
    }

    case "generate:badges": {
      await generateAndWriteBadges();
      break;
    }

    case "generate:readme": {
      await generateAndWriteReadme();
      break;
    }

    default:
      console.error(`Unknown command: ${command}`);
      process.exit(1);
  }
}

if (require.main === module) {
  const args = process.argv.slice(2);
  const command = args[0];

  if (!command) {
    console.error(
      "Please provide a command: fetch:packages, fetch:downloads, generate:report, generate:badges, or generate:readme"
    );
    console.error("\nOptions for fetch:downloads:");
    console.error("  --concurrent, -c <num>   Number of concurrent package downloads (default: 50)");
    console.error("  --delay, -d <ms>         Delay between requests in milliseconds (default: 200)");
    console.error("  --chunk-size, -s <days>  Number of days per chunk (default: 30)");
    console.error("\nExample:");
    console.error("  npm run task:npm fetch:downloads --concurrent 20 --delay 500");
    process.exit(1);
  }

  const options = parseCommandOptions(args.slice(1));

  runCommand(command, options)
    .then(() => {
      console.log("Command completed successfully!");
      process.exit(0);
    })
    .catch((error) => {
      console.error("Command failed:", error);
      process.exit(1);
    });
}

export { runCommand };
