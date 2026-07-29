import type { ToolDefinition } from "@testpilot/types";
import { createLogger } from "@testpilot/shared";

const logger = createLogger("tool-registry");

/**
 * Pure Metadata Registry for Agent Tools.
 * Contains tool schemas, descriptions, and handler identifiers.
 * Does NOT execute tools directly (delegated to ToolExecutor).
 */
export class ToolRegistry {
  private static instance: ToolRegistry;
  private tools: Map<string, ToolDefinition> = new Map();

  private constructor() {}

  public static getInstance(): ToolRegistry {
    if (!ToolRegistry.instance) {
      ToolRegistry.instance = new ToolRegistry();
    }
    return ToolRegistry.instance;
  }

  /** Register metadata for a tool */
  public register(tool: ToolDefinition): void {
    if (this.tools.has(tool.name)) {
      logger.warn({ toolName: tool.name }, "Overwriting tool metadata registration");
    }
    this.tools.set(tool.name, tool);
    logger.debug({ toolName: tool.name, handlerKey: tool.handlerKey }, "Tool metadata registered");
  }

  /** Register multiple tool definitions */
  public registerMany(tools: ToolDefinition[]): void {
    for (const tool of tools) {
      this.register(tool);
    }
  }

  /** Retrieve tool metadata by name */
  public get(name: string): ToolDefinition | undefined {
    return this.tools.get(name);
  }

  /** Get all registered tool definitions */
  public getAll(): ToolDefinition[] {
    return Array.from(this.tools.values());
  }

  /** Get subset of registered tool metadata */
  public getSubset(names: string[]): ToolDefinition[] {
    return names
      .map((name) => this.tools.get(name))
      .filter((t): t is ToolDefinition => t !== undefined);
  }
}

export const toolRegistry = ToolRegistry.getInstance();
