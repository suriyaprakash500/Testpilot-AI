import { Router, type Request, type Response, type NextFunction } from "express";
import crypto from "node:crypto";
import { getDb, projects, eq } from "@testpilot/database";
import { createLogger } from "@testpilot/shared";
import { triggerTestRun } from "./test-runs.js";

const logger = createLogger("webhooks-routes");
const router: Router = Router();

/**
 * Verify GitHub Webhook Signature
 */
function verifySignature(secret: string, header: string, rawBody: string): boolean {
  const hmac = crypto.createHmac("sha256", secret);
  const digest = "sha256=" + hmac.update(rawBody).digest("hex");
  
  try {
    return crypto.timingSafeEqual(Buffer.from(digest, "utf8"), Buffer.from(header, "utf8"));
  } catch (err) {
    return false;
  }
}

/**
 * POST /api/webhooks/github
 * Receiver for GitHub Webhook events
 */
router.post("/github", async (req: Request, res: Response, next: NextFunction) => {
  try {
    const event = req.headers["x-github-event"];
    const signature = req.headers["x-hub-signature-256"];
    const webhookSecret = process.env["GITHUB_WEBHOOK_SECRET"];

    logger.info({ event }, "Received GitHub webhook event");

    // 1. Optional Signature Verification if GITHUB_WEBHOOK_SECRET is configured
    if (webhookSecret && signature && typeof signature === "string") {
      // Cast req as any to retrieve rawBody (buffered in index.ts)
      const rawBody = (req as any).rawBody;
      if (!rawBody || !verifySignature(webhookSecret, signature, rawBody.toString("utf8"))) {
        logger.warn("Invalid webhook signature");
        res.status(401).json({ success: false, error: "Invalid webhook signature" });
        return;
      }
    }

    // 2. Handle Ping Event
    if (event === "ping") {
      res.json({ success: true, message: "pong" });
      return;
    }

    // 3. Process Push & Pull Request Events
    if (event === "push" || event === "pull_request") {
      const payload = req.body;
      const repoUrl = payload.repository?.html_url;

      if (!repoUrl) {
        res.status(400).json({ success: false, error: "Missing repository URL in webhook payload" });
        return;
      }

      // Check actions for pull_request events
      if (event === "pull_request") {
        const action = payload.action;
        // Only trigger on open or code updates
        if (action !== "opened" && action !== "synchronize") {
          logger.info({ action }, "Ignoring pull_request event due to unhandled action");
          res.json({ success: true, message: `Ignored pull request action: ${action}` });
          return;
        }
      }

      const normalizedRepoUrl = repoUrl.toLowerCase().replace(/\.git$/, "");
      const db = getDb();
      
      // Get all active projects
      const activeProjects = await db
        .select()
        .from(projects)
        .where(eq(projects.status, "active"));

      // Match project by repo URL normalization
      const matchedProjects = activeProjects.filter(
        (p) => p.repoUrl.toLowerCase().replace(/\.git$/, "") === normalizedRepoUrl
      );

      if (matchedProjects.length === 0) {
        logger.info({ repoUrl }, "No active projects found matching repository URL");
        res.json({ success: true, message: "No matching active projects" });
        return;
      }

      // Trigger runs for all matching projects
      const triggerPromises = matchedProjects.map(async (project) => {
        try {
          const runId = await triggerTestRun(project.id, "webhook");
          logger.info({ projectId: project.id, runId }, "Triggered test run from webhook");
          return { projectId: project.id, runId, success: true };
        } catch (err: any) {
          logger.error({ err, projectId: project.id }, "Failed to trigger run from webhook");
          return { projectId: project.id, error: err.message, success: false };
        }
      });

      const results = await Promise.all(triggerPromises);
      res.json({
        success: true,
        message: `Processed webhook for ${matchedProjects.length} projects`,
        results,
      });
      return;
    }

    logger.info({ event }, "Unhandled GitHub webhook event");
    res.json({ success: true, message: `Unhandled event type: ${event}` });
  } catch (err) {
    next(err);
  }
});

export { router as webhookRoutes };
