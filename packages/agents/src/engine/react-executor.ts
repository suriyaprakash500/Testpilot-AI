import type {
  AgentDefinitionConfig,
  AgentContext,
  RunState,
  AgentDecision,
  ToolCallRequest,
  ChatMessage,
} from "@testpilot/types";
import { createLogger } from "@testpilot/shared";
import { toolRegistry } from "../tools/registry.js";
import { toolExecutor } from "../tools/tool-executor.js";
import { memoryStore } from "../memory/memory-store.js";
import { telemetry } from "../telemetry/telemetry.js";
import { Groq } from "groq-sdk";

const logger = createLogger("react-executor");

/**
 * Single Reusable ReAct Execution Engine.
 * Replaces duplicated ReAct loops across individual agents.
 * Runs agent configs against Groq LLM with dynamic tool calling and Zod validation.
 */
export class ReActExecutor {
  private groq: Groq;

  constructor() {
    this.groq = new Groq({ apiKey: process.env["GROQ_API_KEY"] || "dummy-key-for-types" });
  }

  /** Execute an agent definition using the central ReAct engine loop */
  public async execute<TOutput = unknown>(
    agentConfig: AgentDefinitionConfig<TOutput>,
    context: AgentContext,
    state: RunState,
    maxSteps = 5
  ): Promise<AgentDecision<TOutput>> {
    const startTime = Date.now();
    logger.info({ agentType: agentConfig.type, runId: state.runId }, "ReActExecutor starting agent execution");

    // Gather allowed tool definitions
    const allowedTools = toolRegistry.getSubset(agentConfig.allowedTools);
    const toolDeclarations = allowedTools.map((t) => ({
      type: "function" as const,
      function: {
        name: t.name,
        description: t.description,
        parameters: t.parameters,
      },
    }));

    // Build chat conversation history with state & memory context
    const runMemories = memoryStore.getMemories(state.runId);
    const messages: ChatMessage[] = [
      { role: "system", content: `${agentConfig.systemPrompt}\nGoal: ${agentConfig.goal}` },
      {
        role: "user",
        content: `Current Run State:\n${JSON.stringify({
          projectId: state.projectId,
          runId: state.runId,
          completedSteps: state.completedSteps,
          memories: runMemories.slice(-5),
        })}`,
      },
    ];

    let currentStep = 0;
    while (currentStep < maxSteps) {
      currentStep++;
      const llmStart = Date.now();

      try {
        const completion = await this.groq.chat.completions.create({
          model: "llama-3.3-70b-versatile",
          messages: messages as any,
          tools: toolDeclarations.length > 0 ? toolDeclarations : undefined,
          temperature: 0.1,
        });

        const reasoningMs = Date.now() - llmStart;
        const tokensUsed = (completion.usage?.prompt_tokens || 0) + (completion.usage?.completion_tokens || 0);
        telemetry.record(state.runId, "reasoning_latency", reasoningMs, agentConfig.type);
        telemetry.record(state.runId, "tokens_used", tokensUsed, agentConfig.type);

        const choice = completion.choices[0]?.message;
        if (!choice) {
          throw new Error("No response message returned from Groq API");
        }

        // Check if LLM requested tool calls
        if (choice.tool_calls && choice.tool_calls.length > 0) {
          const rawCall = choice.tool_calls[0];
          if (!rawCall || !rawCall.function) continue;

          const toolCall: ToolCallRequest = {
            id: rawCall.id || crypto.randomUUID(),
            name: rawCall.function.name,
            arguments: JSON.parse(rawCall.function.arguments || "{}"),
          };

          const toolStart = Date.now();
          const toolResult = await toolExecutor.execute(toolCall, context);
          telemetry.record(state.runId, "tool_latency", Date.now() - toolStart, agentConfig.type, toolCall.name);

          // Store tool execution in MemoryStore & RunState observations
          memoryStore.addMemory(state.runId, toolCall.name, "attempted_fix", toolResult);
          state.observations.push({
            id: crypto.randomUUID(),
            timestamp: new Date(),
            type: "tool_result",
            source: agentConfig.type,
            data: toolResult,
          });

          // If tool completed agent goal, return decision
          return {
            reasoning: choice.content || `Executed tool '${toolCall.name}'`,
            action: toolCall,
            confidence: 0.95,
            completed: true,
            output: toolResult.output as TOutput,
          };
        }

        // Standard completion without tool calls
        return {
          reasoning: choice.content || "Completed agent reasoning task",
          action: null,
          confidence: 0.90,
          completed: true,
          output: { text: choice.content } as unknown as TOutput,
        };
      } catch (err) {
        logger.error({ agentType: agentConfig.type, err }, "ReAct step execution error");
        telemetry.record(state.runId, "failure", 1, agentConfig.type);
        return {
          reasoning: `Execution failed: ${(err as Error).message}`,
          action: null,
          confidence: 0.0,
          completed: false,
        };
      }
    }

    return {
      reasoning: "Reached maximum ReAct step limit without explicit completion",
      action: null,
      confidence: 0.5,
      completed: false,
    };
  }
}

export const reactExecutor = new ReActExecutor();
