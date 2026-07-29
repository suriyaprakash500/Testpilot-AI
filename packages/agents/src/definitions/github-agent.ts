import type { AgentDefinitionConfig } from "@testpilot/types";
import { z } from "zod";

export const githubAgentOutputSchema = z.object({
  success: z.boolean(),
  prUrl: z.string().optional(),
});

export const githubAgentConfig: AgentDefinitionConfig = {
  name: "GitHub Integration Agent",
  type: "github-integration",
  description: "Opens Pull Requests on GitHub containing generated/repaired test cases.",
  systemPrompt: "You are a GitHub integration agent. Commit generated Playwright test files and open clean Pull Requests.",
  allowedTools: ["create_pull_request"],
  supportedEvents: ["SUITE_EXECUTION_PASSED"],
  priority: 10,
  outputSchema: githubAgentOutputSchema,
};
