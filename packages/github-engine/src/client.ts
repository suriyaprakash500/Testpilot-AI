import { Octokit } from "@octokit/rest";
import { createLogger, decrypt } from "@testpilot/shared";
import { getDb, projects, users, eq } from "@testpilot/database";

const logger = createLogger("github-client");

const clients = new Map<string, Octokit>();

/** Get an Octokit client for a user's GitHub token */
export function getGitHubClient(token: string): Octokit {
  if (clients.has(token)) return clients.get(token)!;
  const client = new Octokit({ auth: token });
  clients.set(token, client);
  return client;
}

/** Parse owner and repo from a GitHub URL */
export function parseRepoUrl(url: string): { owner: string; repo: string } {
  const match = url.match(/github\.com\/([^/]+)\/([^/]+?)(?:\.git)?$/);
  if (!match?.[1] || !match?.[2]) {
    throw new Error(`Invalid GitHub URL: ${url}`);
  }
  return { owner: match[1], repo: match[2] };
}

/** Fetch user's token and project details, returning an authenticated Octokit client and repository details */
async function getAuthenticatedClient(projectId: string): Promise<{ octokit: Octokit; owner: string; repo: string }> {
  const db = getDb();
  const [project] = await db.select().from(projects).where(eq(projects.id, projectId));
  if (!project) {
    throw new Error(`Project not found: ${projectId}`);
  }

  const [user] = await db.select().from(users).where(eq(users.id, project.userId));
  if (!user) {
    throw new Error(`User not found for project: ${projectId}`);
  }

  const token = decrypt(user.githubToken);
  const octokit = getGitHubClient(token);
  const { owner, repo } = parseRepoUrl(project.repoUrl);

  return { octokit, owner, repo };
}

/** Create a GitHub issue */
export async function createIssue(
  projectId: string,
  options: { title: string; body: string; labels?: string[] }
): Promise<void> {
  try {
    const { octokit, owner, repo } = await getAuthenticatedClient(projectId);
    logger.info({ projectId, title: options.title, owner, repo }, "Creating GitHub issue");
    
    await octokit.issues.create({
      owner,
      repo,
      title: options.title,
      body: options.body,
      labels: options.labels,
    });
    
    logger.info({ projectId, title: options.title }, "Successfully created GitHub issue");
  } catch (err) {
    logger.error({ err, projectId }, "Error creating GitHub issue");
    throw err;
  }
}

/** Create a PR comment */
export async function createPRComment(
  projectId: string,
  prNumber: number,
  body: string
): Promise<void> {
  try {
    const { octokit, owner, repo } = await getAuthenticatedClient(projectId);
    logger.info({ projectId, prNumber, owner, repo }, "Creating PR comment");

    await octokit.issues.createComment({
      owner,
      repo,
      issue_number: prNumber,
      body,
    });

    logger.info({ projectId, prNumber }, "Successfully created PR comment");
  } catch (err) {
    logger.error({ err, projectId, prNumber }, "Error creating PR comment");
    throw err;
  }
}

