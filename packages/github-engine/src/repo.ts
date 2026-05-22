import { simpleGit } from "simple-git";
import path from "node:path";
import fs from "node:fs/promises";
import { createLogger } from "@testpilot/shared";
import { getDb, projects, eq } from "@testpilot/database";

process.env["GIT_TERMINAL_PROMPT"] = "0";

const logger = createLogger("github-repo");

const REPOS_DIR = process.env["REPOS_DIR"] || "./repos";

/** Clone a repository (shallow, depth=1) */
export async function cloneRepo(projectId: string, repoUrl?: string): Promise<string> {
  const repoPath = path.join(REPOS_DIR, projectId);

  // Check if already cloned
  try {
    await fs.access(path.join(repoPath, ".git"));
    logger.info({ projectId }, "Repo already cloned, pulling latest");
    const git = simpleGit(repoPath);
    await git.pull();
    return repoPath;
  } catch {
    // Not cloned yet
  }

  await fs.mkdir(repoPath, { recursive: true });

  let url = repoUrl;
  if (!url) {
    try {
      const db = getDb();
      const [project] = await db.select().from(projects).where(eq(projects.id, projectId));
      if (project?.repoUrl) {
        url = project.repoUrl;
      }
    } catch (err) {
      logger.error({ err, projectId }, "Failed to fetch project from database");
    }
  }

  if (!url) {
    url = `https://github.com/placeholder/${projectId}`;
  }

  logger.info({ projectId, url }, "Cloning repository");
  const git = simpleGit();
  await git.clone(url, repoPath, ["--depth", "1", "--single-branch"]);

  return repoPath;
}

/** Get a tree of files in the repo */
export async function getFileTree(
  repoPath: string,
  options?: { maxDepth?: number; maxFiles?: number }
): Promise<string> {
  const maxDepth = options?.maxDepth ?? 4;
  const maxFiles = options?.maxFiles ?? 200;
  const lines: string[] = [];
  let fileCount = 0;

  const IGNORE = new Set([
    "node_modules", ".git", ".next", "dist", "build",
    ".cache", "coverage", ".turbo", "__pycache__",
  ]);

  async function walk(dir: string, depth: number, prefix: string) {
    if (depth > maxDepth || fileCount >= maxFiles) return;

    const entries = await fs.readdir(dir, { withFileTypes: true });
    const sorted = entries.sort((a, b) => {
      // Directories first
      if (a.isDirectory() && !b.isDirectory()) return -1;
      if (!a.isDirectory() && b.isDirectory()) return 1;
      return a.name.localeCompare(b.name);
    });

    for (const entry of sorted) {
      if (fileCount >= maxFiles) break;
      if (IGNORE.has(entry.name)) continue;
      if (entry.name.startsWith(".") && entry.name !== ".env.example") continue;

      const isDir = entry.isDirectory();
      lines.push(`${prefix}${isDir ? "📁" : "📄"} ${entry.name}`);
      fileCount++;

      if (isDir) {
        await walk(path.join(dir, entry.name), depth + 1, prefix + "  ");
      }
    }
  }

  await walk(repoPath, 0, "");
  return lines.join("\n");
}

/** Read a file from the repo */
export async function readFile(repoPath: string, filePath: string): Promise<string> {
  const fullPath = path.join(repoPath, filePath);
  return fs.readFile(fullPath, "utf-8");
}
