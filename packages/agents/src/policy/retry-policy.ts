import type { RetryDecision, AgentType } from "@testpilot/types";
import { createLogger } from "@testpilot/shared";

const logger = createLogger("retry-policy");

/**
 * Retry Policy Engine: Evaluates failure events and decides retry actions,
 * exponential backoffs, agent switches, or execution terminations.
 */
export class RetryPolicy {
  private static instance: RetryPolicy;
  private attemptCounts: Map<string, number> = new Map();

  private constructor() {}

  public static getInstance(): RetryPolicy {
    if (!RetryPolicy.instance) {
      RetryPolicy.instance = new RetryPolicy();
    }
    return RetryPolicy.instance;
  }

  /** Evaluate failure context and determine appropriate recovery policy */
  public evaluate(
    runId: string,
    failureType: string,
    currentAgent?: AgentType,
    maxRetries = 3
  ): RetryDecision {
    const key = `${runId}:${failureType}`;
    const attempts = (this.attemptCounts.get(key) || 0) + 1;
    this.attemptCounts.set(key, attempts);

    logger.info({ runId, failureType, attempts, maxRetries }, "Evaluating failure retry policy");

    if (attempts > maxRetries) {
      return {
        action: "terminate",
        delayMs: 0,
        reason: `Maximum retry limit (${maxRetries}) exceeded for failure type '${failureType}'`,
      };
    }

    if (failureType === "selector" && currentAgent === "browser-execution") {
      return {
        action: "switch_agent",
        delayMs: 500,
        suggestedAgent: "failure-analysis",
        reason: "Locator failure detected. Switching from Browser Execution to Failure Diagnostics Agent.",
      };
    }

    // Default exponential backoff
    const delayMs = Math.pow(2, attempts) * 1000;
    return {
      action: "exponential_backoff",
      delayMs,
      reason: `Retrying step after ${delayMs}ms exponential backoff delay (Attempt ${attempts}/${maxRetries})`,
    };
  }

  /** Reset retry counts for a run */
  public reset(runId: string): void {
    for (const key of this.attemptCounts.keys()) {
      if (key.startsWith(`${runId}:`)) {
        this.attemptCounts.delete(key);
      }
    }
  }
}

export const retryPolicy = RetryPolicy.getInstance();
