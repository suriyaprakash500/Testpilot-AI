import time
import json
import logging
from typing import Dict, Any, Optional
from groq import Groq
from app.config import settings
from app.models import AgentDefinitionConfig, AgentDecision, RunState, ToolCallRequest
from app.tools.registry import tool_registry
from app.tools.executor import tool_executor
from app.core.telemetry import telemetry
from app.core.memory_store import memory_store

logger = logging.getLogger("react-executor")

class ReActExecutor:
    def __init__(self):
        self.client = Groq(api_key=settings.groq_api_key)

    async def execute(
        self,
        agent_config: AgentDefinitionConfig,
        context: Dict[str, Any],
        state: RunState,
        max_steps: int = 5
    ) -> AgentDecision:
        logger.info(f"ReActExecutor starting execution for agent {agent_config.name}")

        allowed_tools = tool_registry.get_subset(agent_config.allowed_tools)
        tool_declarations = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters
                }
            }
            for t in allowed_tools
        ]

        messages = [
            {"role": "system", "content": f"{agent_config.system_prompt}\nGoal: {agent_config.description}"},
            {"role": "user", "content": f"Run State: {state.model_dump_json()}"}
        ]

        step = 0
        while step < max_steps:
            step += 1
            start_time = time.time()

            try:
                kwargs = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": messages,
                    "temperature": 0.1
                }
                if tool_declarations:
                    kwargs["tools"] = tool_declarations

                completion = self.client.chat.completions.create(**kwargs)
                latency = time.time() - start_time
                telemetry.record(state.run_id, "reasoning_latency", latency, agent_config.type)

                choice = completion.choices[0].message
                if choice.tool_calls:
                    raw_call = choice.tool_calls[0]
                    tool_call = ToolCallRequest(
                        id=raw_call.id or "call_1",
                        name=raw_call.function.name,
                        arguments=json.loads(raw_call.function.arguments or "{}")
                    )

                    tool_start = time.time()
                    tool_result = await tool_executor.execute(tool_call, context)
                    telemetry.record(state.run_id, "tool_latency", time.time() - tool_start, agent_config.type, tool_call.name)

                    memory_store.add_memory(state.run_id, tool_call.name, "attempted_fix", tool_result.output)
                    return AgentDecision(
                        reasoning=choice.content or f"Executed tool {tool_call.name}",
                        action=tool_call,
                        confidence=0.95,
                        completed=True,
                        output=tool_result.output
                    )

                return AgentDecision(
                    reasoning=choice.content or "Completed reasoning step",
                    action=None,
                    confidence=0.90,
                    completed=True,
                    output={"text": choice.content}
                )

            except Exception as e:
                logger.error(f"ReAct step error: {e}")
                telemetry.record(state.run_id, "failure", 1.0, agent_config.type)
                return AgentDecision(
                    reasoning=f"Execution error: {str(e)}",
                    action=None,
                    confidence=0.0,
                    completed=False
                )

        return AgentDecision(
            reasoning="Reached max steps without explicit completion",
            action=None,
            confidence=0.5,
            completed=False
        )

react_executor = ReActExecutor()
