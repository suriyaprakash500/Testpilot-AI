import type { Page } from "playwright";
import path from "node:path";
import fs from "node:fs/promises";

const ARTIFACTS_DIR = process.env["ARTIFACTS_DIR"] || "./artifacts";

/** Save a screenshot of the current page state */
export async function saveScreenshot(
  page: Page,
  projectId: string,
  runId: string,
  testName: string
): Promise<string> {
  const dir = path.join(ARTIFACTS_DIR, projectId, runId, "screenshots");
  await fs.mkdir(dir, { recursive: true });

  const filename = `${sanitize(testName)}-${Date.now()}.png`;
  const filepath = path.join(dir, filename);

  await page.screenshot({ path: filepath, fullPage: true });
  return filepath;
}

/** Save a trace file */
export async function saveTrace(
  projectId: string,
  runId: string,
  testName: string,
  tracePath: string
): Promise<string> {
  const dir = path.join(ARTIFACTS_DIR, projectId, runId, "traces");
  await fs.mkdir(dir, { recursive: true });

  const filename = `${sanitize(testName)}.trace.zip`;
  const dest = path.join(dir, filename);
  await fs.copyFile(tracePath, dest);
  return dest;
}

/** Get artifact directory for a run */
export function getArtifactDir(projectId: string, runId: string): string {
  return path.join(ARTIFACTS_DIR, projectId, runId);
}

function sanitize(name: string): string {
  return name.replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 100);
}
