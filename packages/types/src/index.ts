// ============================================================
// TestPilot AI — Core Type Definitions
// ============================================================

// --- User & Auth ---

export interface User {
  id: string;
  email: string;
  name: string;
  githubId: string;
  avatarUrl: string | null;
  githubToken: string; // encrypted at rest
  createdAt: Date;
}

// --- Project ---

export type ProjectStatus = "active" | "paused" | "archived";

export interface Project {
  id: string;
  userId: string;
  name: string;
  repoUrl: string;
  websiteUrl: string;
  testEmail?: string | null;
  testPassword?: string | null;
  status: ProjectStatus;
  createdAt: Date;
  updatedAt: Date;
}

// --- Repository Analysis ---

export type Framework =
  | "nextjs"
  | "react"
  | "vue"
  | "nuxt"
  | "angular"
  | "svelte"
  | "astro"
  | "remix"
  | "express"
  | "unknown";

export interface RouteInfo {
  path: string;
  component: string | null;
  isDynamic: boolean;
  methods: string[]; // GET, POST, etc.
}

export interface ComponentInfo {
  name: string;
  filePath: string;
  type: "page" | "layout" | "component" | "api" | "context" | "hook" | "util" | "config";
}

export interface RepoAnalysis {
  id: string;
  projectId: string;
  framework: Framework;
  language: string;
  routes: RouteInfo[];
  components: ComponentInfo[];
  hasAuth: boolean;
  hasApi: boolean;
  entryPoints: string[];
  dependencies: Record<string, string>;
  analyzedAt: Date;
}

// --- Test Planning ---

export type TestPriority = "critical" | "high" | "medium" | "low";
export type TestType = "smoke" | "functional" | "e2e" | "visual" | "accessibility";

export interface TestScenario {
  id: string;
  name: string;
  description: string;
  route: string;
  priority: TestPriority;
  type: TestType;
  steps: string[];
  assertions: string[];
  edgeCases: string[];
}

export interface TestPlan {
  id: string;
  projectId: string;
  testRunId: string;
  scenarios: TestScenario[];
  totalEstimatedDuration: number; // seconds
  createdAt: Date;
}

// --- Test Execution ---

export type TestRunStatus =
  | "pending"
  | "analyzing"
  | "planning"
  | "generating"
  | "executing"
  | "analyzing_failures"
  | "reporting"
  | "completed"
  | "failed"
  | "cancelled";

export type TestRunTrigger = "manual" | "webhook" | "schedule";

export interface TestRun {
  id: string;
  projectId: string;
  status: TestRunStatus;
  trigger: TestRunTrigger;
  startedAt: Date | null;
  completedAt: Date | null;
  summary: TestRunSummary | null;
  createdAt: Date;
}

export interface TestRunSummary {
  total: number;
  passed: number;
  failed: number;
  skipped: number;
  duration: number; // ms
}

export type TestCaseStatus = "pending" | "running" | "passed" | "failed" | "skipped";

export interface TestCase {
  id: string;
  testRunId: string;
  name: string;
  code: string;
  status: TestCaseStatus;
  errorMessage: string | null;
  screenshotPath: string | null;
  tracePath: string | null;
  consoleLogs: string[];
  durationMs: number | null;
  createdAt: Date;
}

// --- Failure Analysis ---

export type FailureType = "assertion" | "timeout" | "selector" | "network" | "script" | "unknown";

export interface FailureReport {
  id: string;
  testCaseId: string;
  type: FailureType;
  message: string;
  stackTrace: string | null;
  screenshotPath: string | null;
  domSnapshot: string | null;
  rootCause: string | null;
  suggestedFix: string | null;
  analysis: Record<string, unknown>;
  createdAt: Date;
}

// --- AI Generation Tracking ---

export type AgentType =
  | "repo-analysis"
  | "test-planning"
  | "playwright-gen"
  | "browser-execution"
  | "failure-analysis"
  | "github-integration";

export interface AIGeneration {
  id: string;
  projectId: string;
  agentType: AgentType;
  promptHash: string;
  model: string;
  inputTokens: number;
  outputTokens: number;
  durationMs: number;
  cached: boolean;
  createdAt: Date;
}

// --- Reports ---

export interface Report {
  id: string;
  testRunId: string;
  htmlPath: string | null;
  jsonData: Record<string, unknown>;
  createdAt: Date;
}

// --- WebSocket Events ---

export type WSEventType =
  | "run:status"
  | "run:progress"
  | "agent:started"
  | "agent:completed"
  | "agent:error"
  | "test:started"
  | "test:completed"
  | "test:failed"
  | "log:entry";

export interface WSEvent {
  type: WSEventType;
  projectId: string;
  runId?: string;
  data: Record<string, unknown>;
  timestamp: Date;
}

// --- API Contracts ---

export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    details?: unknown;
  };
}

export interface CreateProjectRequest {
  repoUrl: string;
  websiteUrl: string;
  name?: string;
}

export interface TriggerRunRequest {
  trigger?: TestRunTrigger;
}

// --- Agent Pipeline ---

export interface AgentContext {
  projectId: string;
  runId: string;
  repoAnalysis?: RepoAnalysis;
  testPlan?: TestPlan;
  testCases?: TestCase[];
  failureReports?: FailureReport[];
  testCredentials?: { email: string; password: string };
}

export interface AgentResult<T = unknown> {
  agentType: AgentType;
  success: boolean;
  data?: T;
  error?: string;
  tokensUsed: number;
  durationMs: number;
}

export * from "./schemas.js";
