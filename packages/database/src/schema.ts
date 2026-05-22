import {
  pgTable,
  uuid,
  varchar,
  text,
  timestamp,
  jsonb,
  integer,
  boolean,
  pgEnum,
} from "drizzle-orm/pg-core";

// ============================================================
// Enums
// ============================================================

export const projectStatusEnum = pgEnum("project_status", ["active", "paused", "archived"]);
export const testRunStatusEnum = pgEnum("test_run_status", [
  "pending", "analyzing", "planning", "generating", "executing",
  "analyzing_failures", "reporting", "completed", "failed", "cancelled",
]);
export const testRunTriggerEnum = pgEnum("test_run_trigger", ["manual", "webhook", "schedule"]);
export const testCaseStatusEnum = pgEnum("test_case_status", [
  "pending", "running", "passed", "failed", "skipped",
]);
export const failureTypeEnum = pgEnum("failure_type", [
  "assertion", "timeout", "selector", "network", "script", "unknown",
]);
export const agentTypeEnum = pgEnum("agent_type", [
  "repo-analysis", "test-planning", "playwright-gen",
  "browser-execution", "failure-analysis", "github-integration",
]);
export const componentTypeEnum = pgEnum("component_type", ["page", "layout", "component", "api"]);

// ============================================================
// Tables
// ============================================================

export const users = pgTable("users", {
  id: uuid("id").primaryKey().defaultRandom(),
  email: varchar("email", { length: 255 }).notNull().unique(),
  name: varchar("name", { length: 255 }).notNull(),
  githubId: varchar("github_id", { length: 50 }).notNull().unique(),
  avatarUrl: text("avatar_url"),
  githubToken: text("github_token").notNull(), // encrypted
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const projects = pgTable("projects", {
  id: uuid("id").primaryKey().defaultRandom(),
  userId: uuid("user_id").notNull().references(() => users.id, { onDelete: "cascade" }),
  name: varchar("name", { length: 255 }).notNull(),
  repoUrl: text("repo_url").notNull(),
  websiteUrl: text("website_url").notNull(),
  status: projectStatusEnum("status").notNull().default("active"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});

export const repositories = pgTable("repositories", {
  id: uuid("id").primaryKey().defaultRandom(),
  projectId: uuid("project_id").notNull().references(() => projects.id, { onDelete: "cascade" }),
  framework: varchar("framework", { length: 50 }).notNull().default("unknown"),
  language: varchar("language", { length: 50 }).notNull().default("unknown"),
  routes: jsonb("routes").notNull().default([]),
  components: jsonb("components").notNull().default([]),
  hasAuth: boolean("has_auth").notNull().default(false),
  hasApi: boolean("has_api").notNull().default(false),
  entryPoints: jsonb("entry_points").notNull().default([]),
  dependencies: jsonb("dependencies").notNull().default({}),
  analysisJson: jsonb("analysis_json"),
  analyzedAt: timestamp("analyzed_at", { withTimezone: true }),
});

export const testRuns = pgTable("test_runs", {
  id: uuid("id").primaryKey().defaultRandom(),
  projectId: uuid("project_id").notNull().references(() => projects.id, { onDelete: "cascade" }),
  status: testRunStatusEnum("status").notNull().default("pending"),
  trigger: testRunTriggerEnum("trigger").notNull().default("manual"),
  summaryJson: jsonb("summary_json"),
  startedAt: timestamp("started_at", { withTimezone: true }),
  completedAt: timestamp("completed_at", { withTimezone: true }),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const testCases = pgTable("test_cases", {
  id: uuid("id").primaryKey().defaultRandom(),
  testRunId: uuid("test_run_id").notNull().references(() => testRuns.id, { onDelete: "cascade" }),
  name: varchar("name", { length: 500 }).notNull(),
  code: text("code").notNull(),
  status: testCaseStatusEnum("status").notNull().default("pending"),
  errorMessage: text("error_message"),
  screenshotPath: text("screenshot_path"),
  tracePath: text("trace_path"),
  consoleLogs: jsonb("console_logs").notNull().default([]),
  durationMs: integer("duration_ms"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const aiGenerations = pgTable("ai_generations", {
  id: uuid("id").primaryKey().defaultRandom(),
  projectId: uuid("project_id").notNull().references(() => projects.id, { onDelete: "cascade" }),
  agentType: agentTypeEnum("agent_type").notNull(),
  promptHash: varchar("prompt_hash", { length: 64 }).notNull(),
  model: varchar("model", { length: 100 }).notNull(),
  inputTokens: integer("input_tokens").notNull().default(0),
  outputTokens: integer("output_tokens").notNull().default(0),
  durationMs: integer("duration_ms").notNull().default(0),
  cached: boolean("cached").notNull().default(false),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const failures = pgTable("failures", {
  id: uuid("id").primaryKey().defaultRandom(),
  testCaseId: uuid("test_case_id").notNull().references(() => testCases.id, { onDelete: "cascade" }),
  type: failureTypeEnum("type").notNull().default("unknown"),
  message: text("message").notNull(),
  stackTrace: text("stack_trace"),
  screenshotPath: text("screenshot_path"),
  domSnapshot: text("dom_snapshot"),
  rootCause: text("root_cause"),
  suggestedFix: text("suggested_fix"),
  analysisJson: jsonb("analysis_json"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const reports = pgTable("reports", {
  id: uuid("id").primaryKey().defaultRandom(),
  testRunId: uuid("test_run_id").notNull().references(() => testRuns.id, { onDelete: "cascade" }),
  htmlPath: text("html_path"),
  jsonData: jsonb("json_data").notNull().default({}),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});
