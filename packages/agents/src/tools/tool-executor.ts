import type { AgentContext, ToolCallRequest, ToolCallResult } from "@testpilot/types";
import { createLogger } from "@testpilot/shared";
import { toolRegistry } from "./registry.js";
import { analyzeRepo, extractInteractiveElements, generateFailureAnalysis } from "@testpilot/prompt-engine";
import { runPlaywrightTest } from "@testpilot/playwright-engine";
import { GitHubEngine } from "@testpilot/github-engine";
import path from "node:path";
import fs from "node:fs/promises";

const logger = createLogger("tool-executor");

type ToolHandler = (args: Record<string, any>, context: AgentContext) => Promise<unknown>;

/**
 * Tool Executor Layer: Decoupled execution engine that maps registered
 * tool metadata handlerKeys to physical system services.
 */
export class ToolExecutor {
  private static instance: ToolExecutor;
  private handlers: Map<string, ToolHandler> = new Map();

  private constructor() {
    this.registerBuiltInHandlers();
  }

  public static getInstance(): ToolExecutor {
    if (!ToolExecutor.instance) {
      ToolExecutor.instance = new ToolExecutor();
    }
    return ToolExecutor.instance;
  }

  /** Register an execution handler for a specific handlerKey */
  public registerHandler(handlerKey: string, handler: ToolHandler): void {
    this.handlers.set(handlerKey, handler);
  }

  /** Execute a tool call request against registered physical services */
  public async execute(call: ToolCallRequest, context: AgentContext): Promise<ToolCallResult> {
    const toolMeta = toolRegistry.get(call.name);
    if (!toolMeta) {
      logger.error({ toolName: call.name }, "Unregistered tool name");
      return {
        toolCallId: call.id,
        toolName: call.name,
        output: null,
        error: `Tool '${call.name}' is not registered in ToolRegistry`,
      };
    }

    const handler = this.handlers.get(toolMeta.handlerKey);
    if (!handler) {
      logger.error({ handlerKey: toolMeta.handlerKey }, "Missing handler implementation");
      return {
        toolCallId: call.id,
        toolName: call.name,
        output: null,
        error: `No execution handler registered for key '${toolMeta.handlerKey}'`,
      };
    }

    try {
      logger.info({ toolName: call.name, handlerKey: toolMeta.handlerKey }, "Executing tool call");
      const output = await handler(call.arguments, context);
      return {
        toolCallId: call.id,
        toolName: call.name,
        output,
      };
    } catch (err) {
      const errorMsg = (err as Error).message;
      logger.error({ toolName: call.name, err }, "Tool execution failed");
      return {
        toolCallId: call.id,
        toolName: call.name,
        output: null,
        error: errorMsg,
      };
    }
  }

  /** Register built-in service handlers (Playwright, Git, Prompts, FS) */
  private registerBuiltInHandlers(): void {
    // 1. Repo Analysis Handler
    this.registerHandler("handler:repo:analyze", async ({ repoUrl }, context) => {
      const reposDir = process.env["REPOS_DIR"] || "./repos";
      const repoName = repoUrl.split("/").pop()?.replace(".git", "") || "repo";
      const localPath = path.resolve(reposDir, `${context.projectId}-${repoName}`);
      return await analyzeRepo(localPath);
    });

    // 2. Read Source File Handler
    this.registerHandler("handler:fs:read-source", async ({ relativePath }, context) => {
      const reposDir = process.env["REPOS_DIR"] || "./repos";
      const repoName = context.repoAnalysis?.projectId || "repo";
      const localPath = path.resolve(reposDir, `${context.projectId}-${repoName}`, relativePath);
      const content = await fs.readFile(localPath, "utf-8");
      return { content: content.slice(0, 5000), truncated: content.length > 5000 };
    });

    // 3. Inspect DOM Nodes Handler
    this.registerHandler("handler:browser:inspect-dom", async ({ url }) => {
      const elements = await extractInteractiveElements(url);
      return { total: elements.length, elements: elements.slice(0, 30) };
    });

    // 4. Run Playwright Suite Handler
    this.registerHandler("handler:browser:run-suite", async ({ testCode, testName }, context) => {
      return await runPlaywrightTest({
        runId: context.runId,
        testName,
        code: testCode,
        websiteUrl: context.websiteUrl || "http://localhost:3000",
      });
    });

    // 5. Repair Locator Handler
    this.registerHandler("handler:healing:repair-locator", async ({ failedSelector, errorMessage, domSnapshot }) => {
      return await generateFailureAnalysis({
        testName: "Failed Test Case",
        errorMessage,
        domSnapshot: domSnapshot || "<div>Element not found</div>",
      });
    });

    // 6. Create GitHub PR Handler
    this.registerHandler("handler:github:create-pr", async ({ repoUrl, githubToken, title, body, files }) => {
      const githubEngine = new GitHubEngine(githubToken);
      const prUrl = await githubEngine.createPullRequest({
        repoUrl,
        branchName: `testpilot/auto-tests-${Date.now()}`,
        title,
        body,
        files,
      });
      return { success: true, prUrl };
    });

    // 7. Authenticate Session Handler
    this.registerHandler("handler:auth:session", async ({ projectId, websiteUrl }) => {
      const { authManager } = await import("../auth/auth-manager.js");
      return await authManager.getOrAuthenticateSession(projectId, websiteUrl);
    });
  }
}

export const toolExecutor = ToolExecutor.getInstance();

