import type { ExecutionPlan, TaskNode } from "@testpilot/types";
import { createLogger } from "@testpilot/shared";

const logger = createLogger("planner");

/**
 * Task Decomposition Engine (Planner).
 * Decomposes high-level test goals into structured task execution graphs.
 */
export class Planner {
  private static instance: Planner;

  private constructor() {}

  public static getInstance(): Planner {
    if (!Planner.instance) {
      Planner.instance = new Planner();
    }
    return Planner.instance;
  }

  /** Generate structured execution plan for a target test run */
  public createExecutionPlan(runId: string, goal: string): ExecutionPlan {
    logger.info({ runId, goal }, "Decomposing high-level goal into execution plan tasks");

    const tasks: TaskNode[] = [
      {
        id: "task-1",
        description: "Analyze code repository and framework routes",
        targetAgent: "repo-analysis",
        status: "pending",
        requiredEventTrigger: "RUN_STARTED",
      },
      {
        id: "task-2",
        description: "Derive test scenarios and assertions",
        targetAgent: "test-planning",
        status: "pending",
        requiredEventTrigger: "REPO_ANALYZED",
      },
      {
        id: "task-3",
        description: "Generate Playwright TypeScript test cases",
        targetAgent: "playwright-gen",
        status: "pending",
        requiredEventTrigger: "PLAN_COMPLETED",
      },
      {
        id: "task-4",
        description: "Execute test suite in Playwright browser",
        targetAgent: "browser-execution",
        status: "pending",
        requiredEventTrigger: "CODE_GENERATED",
      },
      {
        id: "task-5",
        description: "Analyze failures and auto-heal locators if suite fails",
        targetAgent: "failure-analysis",
        status: "pending",
        requiredEventTrigger: "SUITE_EXECUTION_FAILED",
      },
      {
        id: "task-6",
        description: "Open Pull Request with generated/repaired test cases",
        targetAgent: "github-integration",
        status: "pending",
        requiredEventTrigger: "SUITE_EXECUTION_PASSED",
      },
    ];

    return {
      id: crypto.randomUUID(),
      runId,
      goal,
      tasks,
      createdAt: new Date(),
    };
  }
}

export const planner = Planner.getInstance();
