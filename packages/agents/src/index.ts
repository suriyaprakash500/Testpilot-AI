import { agentRegistry } from "./registry/agent-registry.js";
import { repoAgentConfig } from "./definitions/repo-agent.js";
import { planAgentConfig } from "./definitions/plan-agent.js";
import { genAgentConfig } from "./definitions/gen-agent.js";
import { execAgentConfig } from "./definitions/exec-agent.js";
import { failureAgentConfig } from "./definitions/failure-agent.js";
import { githubAgentConfig } from "./definitions/github-agent.js";

// Register all agent capability configurations
agentRegistry.register(repoAgentConfig);
agentRegistry.register(planAgentConfig);
agentRegistry.register(genAgentConfig);
agentRegistry.register(execAgentConfig);
agentRegistry.register(failureAgentConfig);
agentRegistry.register(githubAgentConfig);

export * from "./bus/event-bus.js";
export * from "./artifacts/artifact-store.ts";
export * from "./telemetry/telemetry.js";
export * from "./policy/retry-policy.js";
export * from "./registry/agent-registry.js";
export * from "./planner/planner.js";
export * from "./memory/memory-store.js";
export * from "./engine/react-executor.js";
export * from "./auth/auth-manager.js";
export * from "./auth/credential-store.js";
export * from "./auth/session-cache.js";
export * from "./auth/login-detector.js";
export * from "./tools/registry.js";
export * from "./tools/tool-executor.js";
export * from "./orchestrator.js";
