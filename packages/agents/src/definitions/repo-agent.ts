import type { AgentDefinitionConfig } from "@testpilot/types";
import { z } from "zod";

export const repoAgentOutputSchema = z.object({
  framework: z.string(),
  language: z.string(),
  routesCount: z.number(),
  componentsCount: z.number(),
  hasAuth: z.boolean(),
  hasApi: z.boolean(),
});

export const repoAgentConfig: AgentDefinitionConfig = {
  name: "Repo Analysis Agent",
  type: "repo-analysis",
  description: "Parses repository tree structure, framework conventions, routes, and components.",
  systemPrompt: "You are an expert repository analysis agent. Scan the code structure and summarize frameworks and routes.",
  allowedTools: ["analyze_repo_structure", "read_source_file"],
  supportedEvents: ["RUN_STARTED"],
  priority: 10,
  outputSchema: repoAgentOutputSchema,
};
