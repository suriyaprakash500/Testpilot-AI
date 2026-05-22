import type { GroqMessage } from "../client.js";
import type { RepoAnalysis } from "@testpilot/types";

/** Build prompt for creating a test plan from repo analysis */
export function buildTestPlanningPrompt(context: {
  analysis: RepoAnalysis;
  websiteUrl: string;
}): GroqMessage[] {
  return [
    {
      role: "system",
      content: `You are an expert QA engineer. Given an application analysis, create a prioritized test plan.

You MUST respond with valid JSON only. Follow this schema:
{
  "scenarios": [
    {
      "id": "test-001",
      "name": "Homepage loads correctly",
      "description": "Verify the homepage renders with all key elements",
      "route": "/",
      "priority": "critical" | "high" | "medium" | "low",
      "type": "smoke" | "functional" | "e2e" | "visual" | "accessibility",
      "steps": ["Navigate to /", "Wait for page load", "Check title"],
      "assertions": ["Page title contains expected text", "Navigation is visible"],
      "edgeCases": ["Slow network", "Missing assets"]
    }
  ],
  "totalEstimatedDuration": 120
}

Prioritization rules:
- CRITICAL: Homepage, login, signup, checkout, core user flows
- HIGH: Key feature pages, form submissions, navigation
- MEDIUM: Secondary pages, edge cases in core flows
- LOW: Static content pages, nice-to-have checks

Generate 5-15 test scenarios. Focus on the most important user journeys.
Keep steps actionable and specific to Playwright testing.`,
    },
    {
      role: "user",
      content: `Create a test plan for this application:

Website URL: ${context.websiteUrl}
Framework: ${context.analysis.framework}
Has Auth: ${context.analysis.hasAuth}
Has API: ${context.analysis.hasApi}

Routes:
${context.analysis.routes.map((r) => `  ${r.path} (${r.isDynamic ? "dynamic" : "static"})`).join("\n")}

Key Components:
${context.analysis.components.filter((c) => c.type === "page").map((c) => `  ${c.name} (${c.filePath})`).join("\n")}`,
    },
  ];
}
