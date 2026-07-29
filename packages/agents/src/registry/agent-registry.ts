import type { AgentDefinitionConfig, DomainEvent, AgentType } from "@testpilot/types";
import { createLogger } from "@testpilot/shared";

const logger = createLogger("agent-registry");

/**
 * Capability-Based Agent Registry.
 * Registers agent definitions and allows Supervisor to query handlers dynamically by event domain.
 */
export class AgentRegistry {
  private static instance: AgentRegistry;
  private agents: Map<AgentType, AgentDefinitionConfig> = new Map();

  private constructor() {}

  public static getInstance(): AgentRegistry {
    if (!AgentRegistry.instance) {
      AgentRegistry.instance = new AgentRegistry();
    }
    return AgentRegistry.instance;
  }

  /** Register an agent definition configuration */
  public register(config: AgentDefinitionConfig): void {
    this.agents.set(config.type, config);
    logger.info({ agentType: config.type, supportedEvents: config.supportedEvents }, "Agent definition registered");
  }

  /** Get agent definition by type */
  public get(type: AgentType): AgentDefinitionConfig | undefined {
    return this.agents.get(type);
  }

  /** Get all registered agent definitions */
  public getAll(): AgentDefinitionConfig[] {
    return Array.from(this.agents.values());
  }

  /** Query capability registry: Find best agent definition to handle a specific domain event */
  public getAgentForEvent(eventType: DomainEvent["type"]): AgentDefinitionConfig | undefined {
    const candidates = Array.from(this.agents.values()).filter((agent) =>
      agent.supportedEvents.includes(eventType)
    );

    if (candidates.length === 0) {
      return undefined;
    }

    // Sort by priority (highest priority first)
    candidates.sort((a, b) => b.priority - a.priority);
    return candidates[0];
  }
}

export const agentRegistry = AgentRegistry.getInstance();
