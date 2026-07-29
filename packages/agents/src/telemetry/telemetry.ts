import type { TelemetryEvent, AgentType } from "@testpilot/types";
import { createLogger } from "@testpilot/shared";

const logger = createLogger("telemetry");

/**
 * Dedicated Observability and Telemetry Engine.
 * Tracks metrics: reasoning latency, tool latency, token consumption, retries, and failure rates.
 */
export class TelemetryStore {
  private static instance: TelemetryStore;
  private events: TelemetryEvent[] = [];

  private constructor() {}

  public static getInstance(): TelemetryStore {
    if (!TelemetryStore.instance) {
      TelemetryStore.instance = new TelemetryStore();
    }
    return TelemetryStore.instance;
  }

  /** Record a metric event */
  public record(
    runId: string,
    metric: TelemetryEvent["metric"],
    value: number,
    agentType?: AgentType,
    toolName?: string
  ): void {
    const event: TelemetryEvent = {
      id: crypto.randomUUID(),
      runId,
      metric,
      value,
      agentType,
      toolName,
      timestamp: new Date(),
    };

    this.events.push(event);
    logger.debug({ runId, metric, value, agentType, toolName }, "Telemetry event recorded");
  }

  /** Get telemetry events for a specific run */
  public getEventsForRun(runId: string): TelemetryEvent[] {
    return this.events.filter((e) => e.runId === runId);
  }

  /** Calculate total tokens used for a run */
  public getTotalTokens(runId: string): number {
    return this.events
      .filter((e) => e.runId === runId && e.metric === "tokens_used")
      .reduce((sum, e) => sum + e.value, 0);
  }
}

export const telemetry = TelemetryStore.getInstance();
