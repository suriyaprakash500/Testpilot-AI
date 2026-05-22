import { Router, type Response, type NextFunction } from "express";
import { createProjectSchema } from "@testpilot/types";
import { getDb, projects, eq, testRuns, testCases, inArray, desc } from "@testpilot/database";


import { requireAuth, type AuthRequest } from "../middleware/auth.js";
import { NotFoundError } from "@testpilot/shared";

const router: Router = Router();

/**
 * POST /api/projects
 * Create a new project from repo URL + website URL
 */
router.post("/", requireAuth, async (req: AuthRequest, res: Response, next: NextFunction) => {
  try {
    const input = createProjectSchema.parse(req.body);
    const db = getDb();

    // Extract repo name from URL for default project name
    const repoName = input.repoUrl.split("/").pop()?.replace(".git", "") || "Untitled";

    const [project] = await db.insert(projects).values({
      userId: req.userId!,
      name: input.name || repoName,
      repoUrl: input.repoUrl,
      websiteUrl: input.websiteUrl,
    }).returning();

    res.status(201).json({ success: true, data: project });
  } catch (err) {
    next(err);
  }
});

/**
 * GET /api/projects
 * List all projects for the authenticated user
 */
router.get("/", requireAuth, async (req: AuthRequest, res: Response, next: NextFunction) => {
  try {
    const db = getDb();
    const userProjects = await db
      .select()
      .from(projects)
      .where(eq(projects.userId, req.userId!))
      .orderBy(projects.createdAt);

    res.json({ success: true, data: userProjects });
  } catch (err) {
    next(err);
  }
});

/**
 * GET /api/projects/analytics
 * Get workspace analytics (totals, project stats, recent runs)
 */
router.get("/analytics", requireAuth, async (req: AuthRequest, res: Response, next: NextFunction) => {
  try {
    const db = getDb();

    // Get all user projects
    const userProjects = await db
      .select()
      .from(projects)
      .where(eq(projects.userId, req.userId!));

    if (userProjects.length === 0) {
      return res.json({
        success: true,
        data: {
          averagePassRate: 0,
          totalTimeSavedMs: 0,
          failedRunAlerts: 0,
          projects: [],
          recentRuns: []
        }
      });
    }

    const projectIds = userProjects.map((p) => p.id);

    // Get all runs for these projects
    const runs = await db
      .select()
      .from(testRuns)
      .where(inArray(testRuns.projectId, projectIds))
      .orderBy(desc(testRuns.createdAt));

    if (runs.length === 0) {
      return res.json({
        success: true,
        data: {
          averagePassRate: 0,
          totalTimeSavedMs: 0,
          failedRunAlerts: 0,
          projects: userProjects.map((p) => ({
            id: p.id,
            name: p.name,
            websiteUrl: p.websiteUrl,
            totalRuns: 0,
            passRate: 0,
            status: p.status
          })),
          recentRuns: []
        }
      });
    }

    const runIds = runs.map((r) => r.id);

    // Get all test cases for these runs
    const cases = await db
      .select()
      .from(testCases)
      .where(inArray(testCases.testRunId, runIds));

    // Group test cases by runId
    const casesByRun: Record<string, typeof cases> = {};
    for (const c of cases) {
      let runCases = casesByRun[c.testRunId];
      if (!runCases) {
        runCases = [];
        casesByRun[c.testRunId] = runCases;
      }
      runCases.push(c);
    }

    // Calculate global stats
    const passedCases = cases.filter((c) => c.status === "passed");
    const failedCases = cases.filter((c) => c.status === "failed");
    const totalCases = passedCases.length + failedCases.length;
    const averagePassRate = totalCases > 0 ? Math.round((passedCases.length / totalCases) * 1000) / 10 : 0;

    let totalTimeSavedMs = 0;
    for (const rId of Object.keys(casesByRun)) {
      const runCases = casesByRun[rId];
      if (!runCases) continue;
      const durations = runCases.map((c) => c.durationMs || 0);
      const sumDuration = durations.reduce((a, b) => a + b, 0);
      const maxDuration = Math.max(...durations, 0);
      if (durations.length > 1) {
        totalTimeSavedMs += (sumDuration - maxDuration);
      }
    }

    const failedRunAlerts = runs.filter((r) => r.status === "failed").length;

    // Calculate per-project stats
    const projectStats = userProjects.map((p) => {
      const pRuns = runs.filter((r) => r.projectId === p.id);
      const pRunIds = pRuns.map((r) => r.id);
      const pCases = cases.filter((c) => pRunIds.includes(c.testRunId));

      const pPassed = pCases.filter((c) => c.status === "passed").length;
      const pFailed = pCases.filter((c) => c.status === "failed").length;
      const pTotal = pPassed + pFailed;

      return {
        id: p.id,
        name: p.name,
        websiteUrl: p.websiteUrl,
        totalRuns: pRuns.length,
        passRate: pTotal > 0 ? Math.round((pPassed / pTotal) * 1000) / 10 : 0,
        status: p.status
      };
    });

    // Calculate recent runs details
    const recentRunsDetails = runs.slice(0, 5).map((r) => {
      const p = userProjects.find((proj) => proj.id === r.projectId);
      const rCases = casesByRun[r.id] || [];
      const passed = rCases.filter((c) => c.status === "passed").length;
      const failed = rCases.filter((c) => c.status === "failed").length;

      return {
        id: r.id,
        projectName: p ? p.name : "Unknown",
        status: r.status,
        passedCases: passed,
        failedCases: failed,
        createdAt: r.createdAt
      };
    });

    res.json({
      success: true,
      data: {
        averagePassRate,
        totalTimeSavedMs,
        failedRunAlerts,
        projects: projectStats,
        recentRuns: recentRunsDetails
      }
    });
  } catch (err) {
    next(err);
  }
});

/**
 * GET /api/projects/:id
 * Get a single project by ID
 */
router.get("/:id", requireAuth, async (req: AuthRequest, res: Response, next: NextFunction) => {
  try {
    const db = getDb();
    const id = req.params["id"] as string;
    const [project] = await db
      .select()
      .from(projects)
      .where(eq(projects.id, id));

    if (!project) throw new NotFoundError("Project", id);

    res.json({ success: true, data: project });
  } catch (err) {
    next(err);
  }
});

/**
 * DELETE /api/projects/:id
 * Delete a project
 */
router.delete("/:id", requireAuth, async (req: AuthRequest, res: Response, next: NextFunction) => {
  try {
    const db = getDb();
    const id = req.params["id"] as string;
    const [deleted] = await db
      .delete(projects)
      .where(eq(projects.id, id))
      .returning();

    if (!deleted) throw new NotFoundError("Project", id);

    res.json({ success: true, data: { deleted: true } });
  } catch (err) {
    next(err);
  }
});

export { router as projectRoutes };
