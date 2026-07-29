import type { AgentDefinitionConfig } from "@testpilot/types";
import { z } from "zod";

export const planAgentOutputSchema = z.object({
  totalScenarios: z.number(),
  estimatedDuration: z.number(),
});

export const planAgentConfig: AgentDefinitionConfig = {
  name: "Test Planning Agent",
  type: "test-planning",
  description: "Derives critical E2E user flows, scenarios, and assertions based on repository routes.",
  systemPrompt: "You are an expert test planning agent. Plan resilient end-to-end user scenarios and assertions.",
  allowedTools: ["inspect_dom_nodes"],
  supportedEvents: ["REPO_ANALYZED"],
  priority: 10,
  outputSchema: planAgentOutputSchema,
};
