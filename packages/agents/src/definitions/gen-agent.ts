import type { AgentDefinitionConfig } from "@testpilot/types";
import { z } from "zod";

export const genAgentOutputSchema = z.object({
  testCasesCount: z.number(),
  generatedCode: z.string(),
});

export const genAgentConfig: AgentDefinitionConfig = {
  name: "Playwright Code Generator Agent",
  type: "playwright-gen",
  description: "Generates robust, production-grade Playwright TypeScript code snippets.",
  systemPrompt: "You are an expert Playwright test generator. Generate clean TypeScript Playwright code using resilient locators.",
  allowedTools: ["inspect_dom_nodes"],
  supportedEvents: ["PLAN_COMPLETED"],
  priority: 10,
  outputSchema: genAgentOutputSchema,
};
