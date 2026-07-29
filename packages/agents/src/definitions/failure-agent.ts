import type { AgentDefinitionConfig } from "@testpilot/types";
import { z } from "zod";

export const failureAgentOutputSchema = z.object({
  rootCause: z.string(),
  suggestedFix: z.string(),
  repairedSelector: z.string().nullable(),
});

export const failureAgentConfig: AgentDefinitionConfig = {
  name: "Failure Diagnostics & Auto-Healing Agent",
  type: "failure-analysis",
  description: "Diagnoses stack traces, analyzes DOM snapshots, and repairs broken test locators.",
  systemPrompt: "You are an AI failure analysis agent. Diagnose root causes and generate auto-healed resilient CSS/role locators.",
  allowedTools: ["repair_locator", "inspect_dom_nodes"],
  supportedEvents: ["SUITE_EXECUTION_FAILED"],
  priority: 15,
  outputSchema: failureAgentOutputSchema,
};
