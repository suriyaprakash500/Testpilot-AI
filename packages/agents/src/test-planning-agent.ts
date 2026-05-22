import { BaseAgent } from "./base-agent.js";
import { type AgentContext, type AgentType, type TestPlan, testPlanOutputSchema } from "@testpilot/types";
import { complete, parseJsonResponse, buildTestPlanningPrompt } from "@testpilot/prompt-engine";

export class TestPlanningAgent extends BaseAgent {
  readonly type: AgentType = "test-planning";

  protected async execute(context: AgentContext): Promise<TestPlan> {
    if (!context.repoAnalysis) {
      throw new Error("Repo analysis is required for test planning");
    }

    this.progress("Generating test plan...", 30);

    // We need the website URL from the project — passed via context
    const websiteUrl = (context as AgentContext & { websiteUrl?: string }).websiteUrl || "http://localhost:3000";

    const messages = buildTestPlanningPrompt({
      analysis: context.repoAnalysis,
      websiteUrl,
    });

    const result = await complete(messages, { jsonMode: true });
    this.addTokens(result.inputTokens, result.outputTokens);

    this.progress("Validating test plan...", 70);
    const raw = parseJsonResponse(result.content);
    const parsed = testPlanOutputSchema.parse(raw);

    const plan: TestPlan = {
      id: crypto.randomUUID(),
      projectId: context.projectId,
      testRunId: context.runId,
      scenarios: parsed.scenarios,
      totalEstimatedDuration: parsed.totalEstimatedDuration,
      createdAt: new Date(),
    };

    this.progress(`Generated ${plan.scenarios.length} test scenarios`, 100);
    return plan;
  }
}
