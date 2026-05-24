import { Router, type Response, type NextFunction } from "express";
import { createProjectSchema } from "@testpilot/types";
import { getDb, projects, eq, testRuns, testCases, inArray, desc, and, repositories } from "@testpilot/database";


import { requireAuth, type AuthRequest } from "../middleware/auth.js";
import { NotFoundError } from "@testpilot/shared";

const router: Router = Router();

const isUuid = (str: string) => /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(str);

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
        recentRuns: recentRunsDetails,
        totalRuns: runs.length,
        totalCases: cases.length
      }
    });
  } catch (err) {
    next(err);
  }
});

/**
 * GET /api/projects/active-agents
 * Get active status of agents based on running test runs in database
 */
router.get("/active-agents", requireAuth, async (req: AuthRequest, res: Response, next: NextFunction) => {
  try {
    const db = getDb();
    
    // Find any runs that are not completed, failed, or cancelled
    const activeRuns = await db
      .select()
      .from(testRuns)
      .where(inArray(testRuns.status, ["pending", "analyzing", "planning", "generating", "executing", "analyzing_failures", "reporting"]));
    
    // Determine active agent based on statuses of active runs
    const statuses = activeRuns.map(r => r.status);
    
    res.json({
      success: true,
      data: {
        repoAnalysis: statuses.includes("analyzing"),
        testPlanning: statuses.includes("planning"),
        playwrightGen: statuses.includes("generating"),
        browserExecution: statuses.includes("executing"),
        failureAnalysis: statuses.includes("analyzing_failures"),
        githubIntegration: statuses.includes("reporting") || statuses.includes("pending"),
      }
    });
  } catch (err) {
    next(err);
  }
});

/**
 * GET /api/projects/pipelines
 * Get latest execution statuses for each pipeline type (manual, webhook, schedule)
 */
router.get("/pipelines", requireAuth, async (req: AuthRequest, res: Response, next: NextFunction) => {
  try {
    const db = getDb();
    
    // Get user projects
    const userProjects = await db
      .select()
      .from(projects)
      .where(eq(projects.userId, req.userId!));
      
    if (userProjects.length === 0) {
      return res.json({ 
        success: true, 
        data: { manual: null, webhook: null, schedule: null } 
      });
    }
    
    const projectIds = userProjects.map((p) => p.id);
    
    // Get latest run of each trigger type (manual, webhook, schedule)
    const latestManual = await db
      .select()
      .from(testRuns)
      .where(and(inArray(testRuns.projectId, projectIds), eq(testRuns.trigger, "manual")))
      .orderBy(desc(testRuns.createdAt))
      .limit(1);
      
    const latestWebhook = await db
      .select()
      .from(testRuns)
      .where(and(inArray(testRuns.projectId, projectIds), eq(testRuns.trigger, "webhook")))
      .orderBy(desc(testRuns.createdAt))
      .limit(1);
      
    const latestSchedule = await db
      .select()
      .from(testRuns)
      .where(and(inArray(testRuns.projectId, projectIds), eq(testRuns.trigger, "schedule")))
      .orderBy(desc(testRuns.createdAt))
      .limit(1);

    const getRunDetails = async (run: any) => {
      if (!run) return null;
      
      const cases = await db
        .select()
        .from(testCases)
        .where(eq(testCases.testRunId, run.id));
        
      return {
        id: run.id,
        status: run.status,
        createdAt: run.createdAt,
        completedAt: run.completedAt,
        casesCount: cases.length,
        passedCount: cases.filter(c => c.status === "passed").length,
        failedCount: cases.filter(c => c.status === "failed").length
      };
    };

    res.json({
      success: true,
      data: {
        manual: await getRunDetails(latestManual[0]),
        webhook: await getRunDetails(latestWebhook[0]),
        schedule: await getRunDetails(latestSchedule[0])
      }
    });
  } catch (err) {
    next(err);
  }
});

/**
 * GET /api/projects/active-session
 * Get active run session details if any run is currently executing
 */
router.get("/active-session", requireAuth, async (req: AuthRequest, res: Response, next: NextFunction) => {
  try {
    const db = getDb();
    
    // Get user projects
    const userProjects = await db
      .select()
      .from(projects)
      .where(eq(projects.userId, req.userId!));
      
    if (userProjects.length === 0) {
      return res.json({ success: true, data: null });
    }
    
    const projectIds = userProjects.map((p) => p.id);
    
    // Find the most recent active run (status other than completed, failed, cancelled)
    const [activeRun] = await db
      .select()
      .from(testRuns)
      .where(and(
        inArray(testRuns.projectId, projectIds),
        inArray(testRuns.status, ["pending", "analyzing", "planning", "generating", "executing", "analyzing_failures", "reporting"])
      ))
      .orderBy(desc(testRuns.createdAt))
      .limit(1);
      
    if (!activeRun) {
      return res.json({ success: true, data: null });
    }
    
    const project = userProjects.find(p => p.id === activeRun.projectId);
    
    // Find the latest test case for this run
    const [latestCase] = await db
      .select()
      .from(testCases)
      .where(eq(testCases.testRunId, activeRun.id))
      .orderBy(desc(testCases.createdAt))
      .limit(1);
      
    res.json({
      success: true,
      data: {
        runId: activeRun.id,
        status: activeRun.status,
        projectName: project ? project.name : "Unknown",
        websiteUrl: project ? project.websiteUrl : "about:blank",
        testCaseName: latestCase ? latestCase.name : "Evaluating repository diffs..."
      }
    });
  } catch (err) {
    next(err);
  }
});

/**
 * GET /api/projects/repositories
 * List all connected codebases/repositories with framework and scan details
 */
router.get("/repositories", requireAuth, async (req: AuthRequest, res: Response, next: NextFunction) => {
  try {
    const db = getDb();
    
    // Get user projects
    const userProjects = await db
      .select()
      .from(projects)
      .where(eq(projects.userId, req.userId!));
      
    if (userProjects.length === 0) {
      return res.json({ success: true, data: [] });
    }
    
    const projectIds = userProjects.map((p) => p.id);
    
    // Get corresponding repository records
    const repoRecords = await db
      .select()
      .from(repositories)
      .where(inArray(repositories.projectId, projectIds));
      
    const data = userProjects.map((project) => {
      const repo = repoRecords.find(r => r.projectId === project.id);
      
      // Parse git repo name/domain from URL
      let repoName = project.repoUrl;
      try {
        const cleanUrl = project.repoUrl.replace(/^(https?:\/\/)?(www\.)?/, "");
        repoName = cleanUrl;
      } catch {
        // ignore
      }

      return {
        projectId: project.id,
        repoUrl: project.repoUrl,
        repoName: repoName,
        projectName: project.name,
        framework: repo ? repo.framework : "unknown",
        language: repo ? repo.language : "unknown",
        analyzedAt: repo ? repo.analyzedAt : null,
      };
    });

    res.json({ success: true, data });
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
    const id = req.params["id"] as string;
    if (!isUuid(id)) {
      throw new NotFoundError("Project", id);
    }

    const db = getDb();
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
    const id = req.params["id"] as string;
    if (!isUuid(id)) {
      throw new NotFoundError("Project", id);
    }

    const db = getDb();
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
