import { EventEmitter } from "eventemitter3";
import { createLogger } from "@testpilot/shared";
import type { AgentContext, AgentResult, TestRunStatus, WSEvent } from "@testpilot/types";
import { getDb, repositories, testCases, failures, eq } from "@testpilot/database";
import { RepoAnalysisAgent } from "./repo-analysis-agent.js";
import { TestPlanningAgent } from "./test-planning-agent.js";
import { PlaywrightGenAgent } from "./playwright-gen-agent.js";
import { BrowserExecutionAgent } from "./browser-execution-agent.js";
import { FailureAnalysisAgent } from "./failure-analysis-agent.js";
import { GitHubIntegrationAgent } from "./github-integration-agent.js";

const logger = createLogger("orchestrator");

interface OrchestratorEvents {
  "status": (runId: string, status: TestRunStatus) => void;
  "event": (event: WSEvent) => void;
}

/**
 * Orchestrates the full agent pipeline for a test run.
 * Executes agents sequentially, passing context between them.
 *
 * Pipeline: Analyze → Plan → Generate → Execute → Analyze Failures → GitHub Sync
 */
export class Orchestrator extends EventEmitter<OrchestratorEvents> {
  private repoAgent = new RepoAnalysisAgent();
  private planAgent = new TestPlanningAgent();
  private genAgent = new PlaywrightGenAgent();
  private execAgent = new BrowserExecutionAgent();
  private failureAgent = new FailureAnalysisAgent();
  private githubAgent = new GitHubIntegrationAgent();

  constructor() {
    super();
    // Wire up agent events for broadcasting
    const agents = [
      this.repoAgent, this.planAgent, this.genAgent,
      this.execAgent, this.failureAgent, this.githubAgent,
    ];
    for (const agent of agents) {
      agent.on("agent:progress", (type, message, progress) => {
        this.emit("event", {
          type: "run:progress",
          projectId: "",
          data: { agent: type, message, progress },
          timestamp: new Date(),
        });
      });
    }
  }

  /** Run the complete agent pipeline */
  async execute(
    projectId: string,
    runId: string,
    options: { websiteUrl: string; repoUrl: string; githubToken: string; testCredentials?: { email: string; password: string } }
  ): Promise<{
    results: Map<string, AgentResult>;
    status: TestRunStatus;
  }> {
    const results = new Map<string, AgentResult>();
    const context: AgentContext & { websiteUrl: string } = {
      projectId,
      runId,
      websiteUrl: options.websiteUrl,
      testCredentials: options.testCredentials,
    };

    const updateStatus = (status: TestRunStatus) => {
      this.emit("status", runId, status);
      logger.info({ runId, status }, "Run status changed");
    };

    try {
      // Step 1: Repo Analysis
      updateStatus("analyzing");
      const repoResult = await this.repoAgent.run(context);
      results.set("repo-analysis", repoResult);
      if (!repoResult.success) throw new Error(`Repo analysis failed: ${repoResult.error}`);
      context.repoAnalysis = repoResult.data as AgentContext["repoAnalysis"];

      // Save/update repository profile in database
      if (context.repoAnalysis) {
        try {
          const db = getDb();
          const [existingRepo] = await db.select().from(repositories).where(eq(repositories.projectId, projectId));
          if (existingRepo) {
            await db.update(repositories).set({
              framework: context.repoAnalysis.framework,
              language: context.repoAnalysis.language,
              routes: context.repoAnalysis.routes,
              components: context.repoAnalysis.components,
              hasAuth: context.repoAnalysis.hasAuth,
              hasApi: context.repoAnalysis.hasApi,
              entryPoints: context.repoAnalysis.entryPoints,
              dependencies: context.repoAnalysis.dependencies,
              analysisJson: context.repoAnalysis,
              analyzedAt: new Date(),
            }).where(eq(repositories.id, existingRepo.id));
          } else {
            await db.insert(repositories).values({
              projectId,
              framework: context.repoAnalysis.framework,
              language: context.repoAnalysis.language,
              routes: context.repoAnalysis.routes,
              components: context.repoAnalysis.components,
              hasAuth: context.repoAnalysis.hasAuth,
              hasApi: context.repoAnalysis.hasApi,
              entryPoints: context.repoAnalysis.entryPoints,
              dependencies: context.repoAnalysis.dependencies,
              analysisJson: context.repoAnalysis,
              analyzedAt: new Date(),
            });
          }
          logger.info({ projectId, runId }, "Saved repository analysis to database");
        } catch (dbErr) {
          logger.error({ err: dbErr, projectId, runId }, "Failed to save repository analysis to database");
        }
      }

      // Step 2: Test Planning
      updateStatus("planning");
      const planResult = await this.planAgent.run(context);
      results.set("test-planning", planResult);
      if (!planResult.success) throw new Error(`Test planning failed: ${planResult.error}`);
      context.testPlan = planResult.data as AgentContext["testPlan"];

      // Step 3: Test Generation
      updateStatus("generating");
      const genResult = await this.genAgent.run(context);
      results.set("playwright-gen", genResult);
      if (!genResult.success) throw new Error(`Test generation failed: ${genResult.error}`);
      context.testCases = genResult.data as AgentContext["testCases"];

      // Save generated test cases to database
      if (context.testCases && context.testCases.length > 0) {
        try {
          const db = getDb();
          await db.delete(testCases).where(eq(testCases.testRunId, runId));
          await db.insert(testCases).values(context.testCases.map((tc) => ({
            id: tc.id,
            testRunId: tc.testRunId,
            name: tc.name,
            code: tc.code,
            status: tc.status,
            errorMessage: tc.errorMessage,
            screenshotPath: tc.screenshotPath,
            tracePath: tc.tracePath,
            consoleLogs: tc.consoleLogs,
            durationMs: tc.durationMs,
            createdAt: tc.createdAt,
          })));
          logger.info({ runId, count: context.testCases.length }, "Saved generated test cases to database");
        } catch (dbErr) {
          logger.error({ err: dbErr, runId }, "Failed to save generated test cases to database");
        }
      }

      // Step 4: Test Execution
      updateStatus("executing");
      const execResult = await this.execAgent.run(context);
      results.set("browser-execution", execResult);
      if (!execResult.success) throw new Error(`Test execution failed: ${execResult.error}`);
      context.testCases = execResult.data as AgentContext["testCases"];

      // Update test cases execution results in database
      if (context.testCases && context.testCases.length > 0) {
        try {
          const db = getDb();
          for (const tc of context.testCases) {
            await db.update(testCases).set({
              status: tc.status,
              errorMessage: tc.errorMessage,
              screenshotPath: tc.screenshotPath,
              tracePath: tc.tracePath,
              consoleLogs: tc.consoleLogs,
              durationMs: tc.durationMs,
            }).where(eq(testCases.id, tc.id));
          }
          logger.info({ runId, count: context.testCases.length }, "Updated test cases execution results in database");
        } catch (dbErr) {
          logger.error({ err: dbErr, runId }, "Failed to update test cases execution results in database");
        }
      }

      // Step 5: Failure Analysis (only if there are failures)
      const failedTests = (context.testCases || []).filter((t) => t.status === "failed");
      if (failedTests.length > 0) {
        updateStatus("analyzing_failures");
        const failResult = await this.failureAgent.run(context);
        results.set("failure-analysis", failResult);
        context.failureReports = failResult.data as AgentContext["failureReports"];

        // Save failure reports to database
        if (context.failureReports && context.failureReports.length > 0) {
          try {
            const db = getDb();
            for (const fr of context.failureReports) {
              await db.delete(failures).where(eq(failures.testCaseId, fr.testCaseId));
            }
            await db.insert(failures).values(context.failureReports.map((fr) => ({
              id: fr.id,
              testCaseId: fr.testCaseId,
              type: fr.type,
              message: fr.message,
              stackTrace: fr.stackTrace,
              screenshotPath: fr.screenshotPath,
              domSnapshot: fr.domSnapshot,
              rootCause: fr.rootCause,
              suggestedFix: fr.suggestedFix,
              analysisJson: fr.analysis,
              createdAt: fr.createdAt,
            })));
            logger.info({ runId, count: context.failureReports.length }, "Saved failure reports to database");
          } catch (dbErr) {
            logger.error({ err: dbErr, runId }, "Failed to save failure reports to database");
          }
        }

        // Step 6: GitHub Integration
        updateStatus("reporting");
        const ghResult = await this.githubAgent.run(context);
        results.set("github-integration", ghResult);
      } else {
        updateStatus("reporting");
      }

      updateStatus("completed");
      return { results, status: "completed" };
    } catch (err) {
      logger.error({ err, runId }, "Pipeline failed");
      updateStatus("failed");
      return { results, status: "failed" };
    }
  }
}
