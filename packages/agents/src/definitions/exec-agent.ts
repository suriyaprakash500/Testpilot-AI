import type { AgentDefinitionConfig } from "@testpilot/types";
import { z } from "zod";

export const execAgentOutputSchema = z.object({
  passed: z.boolean(),
  durationMs: z.number(),
  errorMessage: z.string().optional(),
});

export const execAgentConfig: AgentDefinitionConfig = {
  name: "Browser Execution Agent",
  type: "browser-execution",
  description: "Executes Playwright tests in headless browser sandboxes using active AuthSession context.",
  systemPrompt: "You are a browser execution agent. Run Playwright suites using active AuthSessions and report results.",
  allowedTools: ["run_playwright_suite", "authenticate_session"],
  supportedEvents: ["CODE_GENERATED", "LOCATOR_FIXED"],
  priority: 10,
  outputSchema: execAgentOutputSchema,
};
