import { EventEmitter } from "eventemitter3";
import { createLogger, type Logger } from "@testpilot/shared";
import type { AgentType, AgentContext, AgentResult } from "@testpilot/types";

/** Events emitted by agents during execution */
export interface AgentEvents {
  "agent:started": (agentType: AgentType, context: AgentContext) => void;
  "agent:progress": (agentType: AgentType, message: string, progress: number) => void;
  "agent:completed": (agentType: AgentType, result: AgentResult) => void;
  "agent:error": (agentType: AgentType, error: Error) => void;
}

/**
 * Base class for all AI agents.
 * Provides lifecycle management, logging, event emission, and token tracking.
 */
export abstract class BaseAgent extends EventEmitter<AgentEvents> {
  public abstract readonly type: AgentType;
  protected logger: Logger;
  protected tokensUsed = 0;
  protected startTime = 0;

  constructor() {
    super();
    this.logger = createLogger("agent");
  }

  /** Execute the agent's task — called by the orchestrator */
  async run(context: AgentContext): Promise<AgentResult> {
    this.logger = createLogger("agent", { agent: this.type, runId: context.runId });
    this.startTime = Date.now();
    this.tokensUsed = 0;

    this.logger.info("Agent started");
    this.emit("agent:started", this.type, context);

    try {
      const data = await this.execute(context);
      const result: AgentResult = {
        agentType: this.type,
        success: true,
        data,
        tokensUsed: this.tokensUsed,
        durationMs: Date.now() - this.startTime,
      };
      this.logger.info({ durationMs: result.durationMs, tokensUsed: result.tokensUsed }, "Agent completed");
      this.emit("agent:completed", this.type, result);
      return result;
    } catch (err) {
      const error = err instanceof Error ? err : new Error(String(err));
      this.logger.error({ err: error }, "Agent failed");
      this.emit("agent:error", this.type, error);
      return {
        agentType: this.type,
        success: false,
        error: error.message,
        tokensUsed: this.tokensUsed,
        durationMs: Date.now() - this.startTime,
      };
    }
  }

  /** Subclasses implement their core logic here */
  protected abstract execute(context: AgentContext): Promise<unknown>;

  /** Report progress to listeners */
  protected progress(message: string, pct: number) {
    this.emit("agent:progress", this.type, message, pct);
  }

  /** Track tokens used by AI calls */
  protected addTokens(input: number, output: number) {
    this.tokensUsed += input + output;
  }
}
