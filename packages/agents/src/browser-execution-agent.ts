import { BaseAgent } from "./base-agent.js";
import type { AgentContext, AgentType, TestCase } from "@testpilot/types";
import { runTest, authenticateAndSave } from "@testpilot/playwright-engine";

export class BrowserExecutionAgent extends BaseAgent {
  readonly type: AgentType = "browser-execution";

  protected async execute(context: AgentContext): Promise<TestCase[]> {
    if (!context.testCases || context.testCases.length === 0) {
      throw new Error("Test cases are required for execution");
    }

    const results: TestCase[] = [];
    const ctx = context as AgentContext & { websiteUrl?: string };

    // Auto-authenticate if credentials are available and the app has auth
    let storageStatePath: string | undefined;
    if (context.testCredentials && context.repoAnalysis?.hasAuth) {
      this.progress("Authenticating browser session...", 5);
      const authPath = await authenticateAndSave({
        websiteUrl: ctx.websiteUrl || "http://localhost:3000",
        email: context.testCredentials.email,
        password: context.testCredentials.password,
        projectId: context.projectId,
        runId: context.runId,
      });
      if (authPath) {
        storageStatePath = authPath;
        this.progress("Authentication successful", 10);
      } else {
        this.progress("Auto-login failed, running tests without auth", 10);
      }
    }

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
        storageStatePath,
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
