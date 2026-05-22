import { BaseAgent } from "./base-agent.js";
import { type AgentContext, type AgentType, type FailureReport, failureAnalysisOutputSchema } from "@testpilot/types";
import { complete, parseJsonResponse, buildFailureAnalysisPrompt } from "@testpilot/prompt-engine";

export class FailureAnalysisAgent extends BaseAgent {
  readonly type: AgentType = "failure-analysis";

  protected async execute(context: AgentContext): Promise<FailureReport[]> {
    const failedTests = (context.testCases || []).filter((t) => t.status === "failed");

    if (failedTests.length === 0) {
      this.progress("No failures to analyze", 100);
      return [];
    }

    const reports: FailureReport[] = [];

    for (let i = 0; i < failedTests.length; i++) {
      const testCase = failedTests[i]!;
      this.progress(
        `Analyzing failure ${i + 1}/${failedTests.length}: ${testCase.name}`,
        Math.round(((i + 1) / failedTests.length) * 100)
      );

      const messages = buildFailureAnalysisPrompt({
        testName: testCase.name,
        testCode: testCase.code,
        errorMessage: testCase.errorMessage || "Unknown error",
        stackTrace: null,
        consoleLogs: testCase.consoleLogs,
      });

      const result = await complete(messages, { jsonMode: true });
      this.addTokens(result.inputTokens, result.outputTokens);

      const raw = parseJsonResponse(result.content);
      const parsed = failureAnalysisOutputSchema.parse(raw);

      reports.push({
        id: crypto.randomUUID(),
        testCaseId: testCase.id,
        type: parsed.type,
        message: testCase.errorMessage || "Unknown error",
        stackTrace: null,
        screenshotPath: testCase.screenshotPath,
        domSnapshot: null,
        rootCause: parsed.rootCause,
        suggestedFix: parsed.suggestedFix,
        analysis: parsed.details || {},
        createdAt: new Date(),
      });
    }

    this.progress(`Analyzed ${reports.length} failures`, 100);
    return reports;
  }
}
