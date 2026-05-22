import { BaseAgent } from "./base-agent.js";
import { type AgentContext, type AgentType, type TestCase, playwrightTestOutputSchema } from "@testpilot/types";
import { complete, parseJsonResponse, buildTestGenerationPrompt } from "@testpilot/prompt-engine";

export class PlaywrightGenAgent extends BaseAgent {
  readonly type: AgentType = "playwright-gen";

  protected async execute(context: AgentContext): Promise<TestCase[]> {
    if (!context.repoAnalysis || !context.testPlan) {
      throw new Error("Repo analysis and test plan are required for test generation");
    }

    const websiteUrl = (context as AgentContext & { websiteUrl?: string }).websiteUrl || "http://localhost:3000";
    const scenarios = context.testPlan.scenarios;
    const testCases: TestCase[] = [];

    for (let i = 0; i < scenarios.length; i++) {
      const scenario = scenarios[i]!;
      this.progress(
        `Generating test ${i + 1}/${scenarios.length}: ${scenario.name}`,
        Math.round(((i + 1) / scenarios.length) * 100)
      );

      const messages = buildTestGenerationPrompt({
        scenario,
        websiteUrl,
        framework: context.repoAnalysis.framework,
      });

      const result = await complete(messages, { jsonMode: true });
      this.addTokens(result.inputTokens, result.outputTokens);

      const raw = parseJsonResponse(result.content);
      const parsed = playwrightTestOutputSchema.parse(raw);

      testCases.push({
        id: crypto.randomUUID(),
        testRunId: context.runId,
        name: parsed.testName,
        code: parsed.testCode,
        status: "pending",
        errorMessage: null,
        screenshotPath: null,
        tracePath: null,
        consoleLogs: [],
        durationMs: null,
        createdAt: new Date(),
      });
    }

    this.progress(`Generated ${testCases.length} tests`, 100);
    return testCases;
  }
}
