import { BaseAgent } from "./base-agent.js";
import type { AgentContext, AgentType, TestCase } from "@testpilot/types";
import { runTest } from "@testpilot/playwright-engine";

export class BrowserExecutionAgent extends BaseAgent {
  readonly type: AgentType = "browser-execution";

  protected async execute(context: AgentContext): Promise<TestCase[]> {
    if (!context.testCases || context.testCases.length === 0) {
      throw new Error("Test cases are required for execution");
    }

    const results: TestCase[] = [];
    const ctx = context as AgentContext & { websiteUrl?: string };

    for (let i = 0; i < context.testCases.length; i++) {
      const testCase = context.testCases[i]!;
      this.progress(
        `Executing test ${i + 1}/${context.testCases.length}: ${testCase.name}`,
        Math.round(((i + 1) / context.testCases.length) * 100)
      );

      const result = await runTest({
        testCode: testCase.code,
        testName: testCase.name,
        projectId: context.projectId,
        runId: context.runId,
        websiteUrl: ctx.websiteUrl,
      });

      results.push({
        ...testCase,
        status: result.passed ? "passed" : "failed",
        errorMessage: result.error || null,
        screenshotPath: result.screenshotPath || null,
        tracePath: result.tracePath || null,
        consoleLogs: result.consoleLogs,
        durationMs: result.durationMs,
      });
    }

    const passed = results.filter((r) => r.status === "passed").length;
    const failed = results.filter((r) => r.status === "failed").length;
    this.progress(`Execution complete: ${passed} passed, ${failed} failed`, 100);

    return results;
  }
}
