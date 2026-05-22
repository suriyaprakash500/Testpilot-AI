import { Router, type Response, type NextFunction } from "express";
import { getDb, testRuns, testCases, projects, users, eq, failures, inArray } from "@testpilot/database";


import { requireAuth, type AuthRequest } from "../middleware/auth.js";
import { NotFoundError, decrypt } from "@testpilot/shared";
import { Orchestrator } from "@testpilot/agents";
import { createLogger } from "@testpilot/shared";

const logger = createLogger("test-run-routes");
const router: Router = Router();

/**
 * Helper to trigger a test run for a project
 */
export async function triggerTestRun(projectId: string, triggerType: "manual" | "webhook" | "schedule"): Promise<string> {
  const db = getDb();

  // Verify project exists
  const [project] = await db.select().from(projects).where(eq(projects.id, projectId));
  if (!project) throw new NotFoundError("Project", projectId);

  // Create test run record
  const [run] = await db.insert(testRuns).values({
    projectId,
    status: "pending",
    trigger: triggerType,
  }).returning();

  // Start orchestrator in background (don't await)
  const orchestrator = new Orchestrator();

  let updateQueue = Promise.resolve();

  const queueUpdate = (fn: () => Promise<void>) => {
    updateQueue = updateQueue.then(fn).catch((err) => {
      logger.error({ err, runId: run!.id }, "Error in test run status update queue");
    });
  };

  orchestrator.on("status", (runId, status) => {
    queueUpdate(async () => {
      try {
        const [currentRun] = await db.select({ status: testRuns.status }).from(testRuns).where(eq(testRuns.id, runId));
        if (currentRun && (currentRun.status === "completed" || currentRun.status === "failed")) {
          if (status !== "completed" && status !== "failed") {
            logger.warn({ runId, status, currentStatus: currentRun.status }, "Skipping status update: run already completed/failed");
            return;
          }
        }
        await db.update(testRuns).set({ status }).where(eq(testRuns.id, runId));
      } catch (err) {
        logger.error({ err, runId, status }, "Failed to update test run status");
      }
    });
  });

  // Fetch project owner's token from database
  const [user] = await db.select().from(users).where(eq(users.id, project.userId));
  if (!user) throw new NotFoundError("User", project.userId);
  const decryptedToken = decrypt(user.githubToken);

  // Fire and forget — the orchestrator runs asynchronously
  orchestrator.execute(projectId, run!.id, {
    websiteUrl: project.websiteUrl,
    repoUrl: project.repoUrl,
    githubToken: decryptedToken,
  }).then(async ({ results, status }) => {
    logger.info({ runId: run!.id, status }, "Test run completed");
    queueUpdate(async () => {
      await db.update(testRuns).set({
        status,
        completedAt: new Date(),
      }).where(eq(testRuns.id, run!.id));
    });
  }).catch((err) => {
    logger.error({ err, runId: run!.id }, "Test run failed");
    queueUpdate(async () => {
      await db.update(testRuns).set({
        status: "failed",
        completedAt: new Date(),
      }).where(eq(testRuns.id, run!.id));
    });
  });

  return run!.id;
}

/**
 * POST /api/test-runs/:projectId/start
 * Trigger a new test run for a project
 */
router.post("/:projectId/start", requireAuth, async (req: AuthRequest, res: Response, next: NextFunction) => {
  try {
    const projectId = req.params["projectId"] as string;

    const runId = await triggerTestRun(projectId, "manual");

    res.status(202).json({
      success: true,
      data: { runId, status: "pending", message: "Test run started" },
    });
  } catch (err) {
    next(err);
  }
});

/**
 * GET /api/test-runs/:projectId
 * List all runs for a project
 */
router.get("/:projectId", requireAuth, async (req: AuthRequest, res: Response, next: NextFunction) => {
  try {
    const db = getDb();
    const projectId = req.params["projectId"] as string;
    const runs = await db
      .select()
      .from(testRuns)
      .where(eq(testRuns.projectId, projectId))
      .orderBy(testRuns.createdAt);

    res.json({ success: true, data: runs });
  } catch (err) {
    next(err);
  }
});

/**
 * GET /api/test-runs/run/:runId
 * Get run details with test cases
 */
router.get("/run/:runId", requireAuth, async (req: AuthRequest, res: Response, next: NextFunction) => {
  try {
    const db = getDb();
    const runId = req.params["runId"] as string;

    const [run] = await db.select().from(testRuns).where(eq(testRuns.id, runId));
    if (!run) throw new NotFoundError("TestRun", runId);

    const cases = await db.select().from(testCases).where(eq(testCases.testRunId, runId));

    const caseIds = cases.map((c) => c.id);
    const runFailures = caseIds.length > 0
      ? await db.select().from(failures).where(inArray(failures.testCaseId, caseIds))
      : [];

    const mappedCases = cases.map((tc) => {
      const failure = runFailures.find((f) => f.testCaseId === tc.id);

      let aiLogs = "";
      if (failure) {
        if (failure.rootCause) {
          aiLogs += `Root Cause:\n${failure.rootCause}\n\n`;
        }
        if (failure.suggestedFix) {
          aiLogs += `Suggested Fix:\n${failure.suggestedFix}`;
        }
      }

      return {
        id: tc.id,
        testRunId: tc.testRunId,
        name: tc.name,
        status: tc.status,
        duration: tc.durationMs || 0,
        error: tc.errorMessage,
        logs: aiLogs || null,
        screenshotUrl: tc.screenshotPath ? `/api/artifacts/${tc.screenshotPath}` : null,
        createdAt: tc.createdAt,
      };
    });

    res.json({ success: true, data: { run, testCases: mappedCases } });
  } catch (err) {
    next(err);
  }
});

/**
 * DELETE /api/test-runs/run/:runId
 * Delete a particular test run and all cascaded data
 */
router.delete("/run/:runId", requireAuth, async (req: AuthRequest, res: Response, next: NextFunction) => {
  try {
    const db = getDb();
    const runId = req.params["runId"] as string;

    const [run] = await db
      .select()
      .from(testRuns)
      .where(eq(testRuns.id, runId));

    if (!run) {
      throw new NotFoundError("TestRun", runId);
    }

    const [project] = await db
      .select()
      .from(projects)
      .where(eq(projects.id, run.projectId));

    if (!project) {
      throw new NotFoundError("Project", run.projectId);
    }

    if (project.userId !== req.userId!) {
      return res.status(403).json({ success: false, error: "Unauthorized to delete this test run" });
    }

    const [deleted] = await db
      .delete(testRuns)
      .where(eq(testRuns.id, runId))
      .returning();

    res.json({ success: true, data: { deleted: !!deleted } });
  } catch (err) {
    next(err);
  }
});

export { router as testRunRoutes };
