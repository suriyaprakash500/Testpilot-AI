import { EventEmitter } from "eventemitter3";
import { createLogger } from "@testpilot/shared";
import type { AgentContext, TestRunStatus, WSEvent, RunState, DomainEvent } from "@testpilot/types";
import { eventBus } from "./bus/event-bus.js";
import { agentRegistry } from "./registry/agent-registry.js";
import { planner } from "./planner/planner.js";
import { retryPolicy } from "./policy/retry-policy.js";
import { reactExecutor } from "./engine/react-executor.js";
import { memoryStore } from "./memory/memory-store.js";
import { artifactStore } from "./artifacts/artifact-store.js";
import { telemetry } from "./telemetry/telemetry.js";
import { authManager } from "./auth/auth-manager.js";

const logger = createLogger("orchestrator");

interface OrchestratorEvents {
  "status": (runId: string, status: TestRunStatus) => void;
  "event": (event: WSEvent) => void;
}

/**
 * Event-Driven Supervisor Router.
 * Replaces hardcoded linear loops with an event-driven subscriber architecture.
 * Listens to domain events on EventBus, evaluates state, queries AgentRegistry,
 * applies RetryPolicy on failures, and delegates execution to ReActExecutor.
 */
export class Orchestrator extends EventEmitter<OrchestratorEvents> {
  private activeStates: Map<string, RunState> = new Map();

  constructor() {
    super();
    this.subscribeToDomainEvents();
  }

  /** Subscribe EventSupervisor to system domain events on EventBus */
  private subscribeToDomainEvents(): void {
    eventBus.subscribe("*", async (event: DomainEvent) => {
      const runId = (event as any).runId;
      if (!runId) return;

      const state = this.activeStates.get(runId);
      if (!state) return;

      logger.info({ eventType: event.type, runId }, "Supervisor handling domain event");

      // Handle terminal failure events
      if (event.type === "RUN_FAILED") {
        state.status = "failed";
        this.emit("status", runId, "failed");
        return;
      }

      // Handle failure events through RetryPolicy
      if (event.type === "SUITE_EXECUTION_FAILED") {
        const failureType = event.failedSelector ? "selector" : "execution";
        const decision = retryPolicy.evaluate(runId, failureType, state.activeAgent || undefined);

        logger.info({ decision, runId }, "RetryPolicy decision evaluated for failure event");

        if (decision.action === "terminate") {
          eventBus.publish({ type: "RUN_FAILED", runId, reason: decision.reason });
          return;
        }

        if (decision.action === "switch_agent" && decision.suggestedAgent) {
          const failureAgent = agentRegistry.get(decision.suggestedAgent);
          if (failureAgent) {
            state.activeAgent = failureAgent.type;
            const agentContext: AgentContext = { projectId: state.projectId, runId };
            await reactExecutor.execute(failureAgent, agentContext, state);
            return;
          }
        }
      }

      // Query capability-based AgentRegistry for candidate handler agent
      const targetAgentConfig = agentRegistry.getAgentForEvent(event.type);
      if (targetAgentConfig) {
        state.activeAgent = targetAgentConfig.type;
        state.iteration++;
        state.updatedAt = new Date();

        const agentContext: AgentContext = { projectId: state.projectId, runId };
        const decision = await reactExecutor.execute(targetAgentConfig, agentContext, state);

        if (decision.completed && decision.confidence >= 0.7) {
          state.completedSteps.push(targetAgentConfig.type);
          this.emit("event", {
            type: "agent:completed",
            projectId: state.projectId,
            runId,
            data: { agent: targetAgentConfig.type, decision },
            timestamp: new Date(),
          });
        }
      }
    });
  }

  /** Initialize and run the autonomous event-driven test run supervisor */
  async execute(
    projectId: string,
    runId: string,
    options: { websiteUrl: string; repoUrl: string; githubToken: string; testCredentials?: { email: string; password: string } }
  ): Promise<{ status: TestRunStatus }> {
    logger.info({ projectId, runId }, "Supervisor starting execution pipeline");

    const initialState: RunState = {
      runId,
      projectId,
      status: "analyzing",
      activeAgent: null,
      completedSteps: [],
      observations: [],
      artifacts: {},
      iteration: 0,
      updatedAt: new Date(),
    };

    this.activeStates.set(runId, initialState);
    this.emit("status", runId, "analyzing");

    // 1. Create Execution Plan using Planner
    const plan = planner.createExecutionPlan(runId, "Analyze repo, generate Playwright tests, execute suite, and open PR");
    memoryStore.addMemory(runId, "execution_plan", "generated_test", plan);

    // 2. Pre-authenticate session if website URL provided (Fail-Fast Verification)
    try {
      if (options.websiteUrl) {
        await authManager.getOrAuthenticateSession(projectId, options.websiteUrl, "form");
      }
    } catch (err) {
      logger.error({ runId, err }, "Pre-authentication failed. Aborting run.");
      initialState.status = "failed";
      this.emit("status", runId, "failed");
      return { status: "failed" };
    }

    // 3. Publish initial domain event to kick off EventBus routing
    eventBus.publish({ type: "RUN_STARTED", runId, projectId });

    return { status: initialState.status };
  }
}
