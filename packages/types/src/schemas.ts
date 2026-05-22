import { z } from "zod";

// ============================================================
// Zod Schemas — Runtime validation for all core types
// ============================================================

export const createProjectSchema = z.object({
  repoUrl: z
    .string()
    .url()
    .regex(/github\.com\/[\w.-]+\/[\w.-]+/, "Must be a valid GitHub repository URL"),
  websiteUrl: z.string().url("Must be a valid URL"),
  name: z.string().min(1).max(100).optional(),
});

export const triggerRunSchema = z.object({
  trigger: z.enum(["manual", "webhook", "schedule"]).default("manual"),
});

export const repoAnalysisOutputSchema = z.object({
  framework: z.enum([
    "nextjs", "react", "vue", "nuxt", "angular", "svelte", "astro", "remix", "express", "unknown",
  ]),
  language: z.string(),
  routes: z.array(
    z.object({
      path: z.string(),
      component: z.string().nullable(),
      isDynamic: z.boolean(),
      methods: z.array(z.string()),
    })
  ),
  components: z.array(
    z.object({
      name: z.string(),
      filePath: z.string(),
      type: z.enum(["page", "layout", "component", "api"]),
    })
  ),
  hasAuth: z.boolean(),
  hasApi: z.boolean(),
  entryPoints: z.array(z.string()),
  dependencies: z.record(z.string()),
});

export const testScenarioSchema = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  route: z.string(),
  priority: z.enum(["critical", "high", "medium", "low"]),
  type: z.enum(["smoke", "functional", "e2e", "visual", "accessibility"]),
  steps: z.array(z.string()),
  assertions: z.array(z.string()),
  edgeCases: z.array(z.string()),
});

export const testPlanOutputSchema = z.object({
  scenarios: z.array(testScenarioSchema),
  totalEstimatedDuration: z.number(),
});

export const playwrightTestOutputSchema = z.object({
  testName: z.string(),
  testCode: z.string(),
  locators: z.array(z.string()),
});

export const failureAnalysisOutputSchema = z.object({
  type: z.enum(["assertion", "timeout", "selector", "network", "script", "unknown"]),
  rootCause: z.string(),
  suggestedFix: z.string(),
  confidence: z.number().min(0).max(1),
  details: z.record(z.unknown()).optional(),
});

export type CreateProjectInput = z.infer<typeof createProjectSchema>;
export type TriggerRunInput = z.infer<typeof triggerRunSchema>;
export type RepoAnalysisOutput = z.infer<typeof repoAnalysisOutputSchema>;
export type TestPlanOutput = z.infer<typeof testPlanOutputSchema>;
export type PlaywrightTestOutput = z.infer<typeof playwrightTestOutputSchema>;
export type FailureAnalysisOutput = z.infer<typeof failureAnalysisOutputSchema>;
