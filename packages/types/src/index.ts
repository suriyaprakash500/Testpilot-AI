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

// --- ReAct Agent, Memory & Event Definitions ---

export interface Observation {
  id: string;
  timestamp: Date;
  type: "tool_result" | "system_event" | "agent_output";
  source: string;
  data: unknown;
}

export interface MemoryItem {
  id: string;
  runId: string;
  key: string;
  type: "failure" | "attempted_fix" | "dom_snapshot" | "generated_test";
  content: unknown;
  timestamp: Date;
}

export interface RunState {
  runId: string;
  projectId: string;
  status: TestRunStatus;
  activeAgent: AgentType | null;
  completedSteps: string[];
  observations: Observation[];
  artifacts: Record<string, string>;
  iteration: number;
  updatedAt: Date;
}

export interface ToolCallRequest {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
}

export interface ToolCallResult {
  toolCallId: string;
  toolName: string;
  output: unknown;
  error?: string;
}

export interface ChatMessage {
  role: "system" | "user" | "assistant" | "tool";
  content: string;
  toolCalls?: ToolCallRequest[];
  toolCallId?: string;
  name?: string;
}

export interface AgentDecision<TOutput = unknown> {
  reasoning: string;
  action: ToolCallRequest | null;
  confidence: number; // 0.0 to 1.0
  completed: boolean;
  output?: TOutput;
}

export interface ToolDefinition<TParams = any> {
  name: string;
  description: string;
  handlerKey: string;
  parameters: Record<string, unknown>;
}

// --- Architecture Types: Bus, Artifacts, Telemetry, Registry & Planner ---

export interface ArtifactRef {
  id: string;
  runId: string;
  type: "screenshot" | "html_trace" | "video" | "generated_code" | "log";
  mimeType: string;
  sizeBytes: number;
  storagePath: string; // S3 bucket key or local path reference
  createdAt: Date;
}

export interface TelemetryEvent {
  id: string;
  runId: string;
  agentType?: AgentType;
  toolName?: string;
  metric: "reasoning_latency" | "tool_latency" | "tokens_used" | "retries" | "failure";
  value: number;
  timestamp: Date;
}

export type RetryAction = "retry" | "exponential_backoff" | "switch_agent" | "terminate";

export interface RetryDecision {
  action: RetryAction;
  delayMs: number;
  reason: string;
  suggestedAgent?: AgentType;
}

export interface TaskNode {
  id: string;
  description: string;
  targetAgent: AgentType;
  status: "pending" | "in_progress" | "completed" | "failed";
  requiredEventTrigger: string;
}

export interface ExecutionPlan {
  id: string;
  runId: string;
  goal: string;
  tasks: TaskNode[];
  createdAt: Date;
}

export interface AgentDefinitionConfig<TOutput = unknown> {
  name: string;
  type: AgentType;
  description: string;
  systemPrompt: string;
  allowedTools: string[];
  supportedEvents: string[];
  priority: number;
  outputSchema?: any; // Zod schema for validation
}

export type DomainEvent =
  | { type: "RUN_STARTED"; runId: string; projectId: string }
  | { type: "REPO_ANALYZED"; runId: string; data: RepoAnalysis }
  | { type: "PLAN_COMPLETED"; runId: string; data: TestPlan }
  | { type: "CODE_GENERATED"; runId: string; data: TestCase[] }
  | { type: "SUITE_EXECUTION_PASSED"; runId: string }
  | { type: "SUITE_EXECUTION_FAILED"; runId: string; errors: string[]; failedSelector?: string; errorMessage?: string }
  | { type: "LOCATOR_FIXED"; runId: string; selector: string; fixedCode?: string }
  | { type: "PR_CREATED"; runId: string; prUrl: string }
  | { type: "RUN_FAILED"; runId: string; reason: string };

// --- Enterprise Authentication Subsystem Definitions ---

export type AuthStrategyType = "form" | "oauth" | "cookie" | "header" | "api_key";

export interface AuthSession {
  id: string;
  projectId: string;
  strategy: AuthStrategyType;
  storageStatePath?: string;
  cookies?: Array<Record<string, unknown>>;
  headers?: Record<string, string>;
  createdAt: Date;
  expiresAt: Date;
}

export interface CredentialRef {
  id: string;
  projectId: string;
  type: AuthStrategyType;
  usernameKey?: string;
  passwordKey?: string;
  secretTokenKey?: string;
}

export interface LoginDetectionResult {
  isLoginForm: boolean;
  detectedBy: "heuristic" | "llm";
  formSelector?: string;
  usernameSelector?: string;
  passwordSelector?: string;
  submitSelector?: string;
  confidence: number;
}

export * from "./schemas.js";




