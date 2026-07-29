import logging
from typing import Dict, Any
from app.models import RunState, DomainEvent
from app.core.bus import event_bus
from app.core.planner import planner
from app.core.retry_policy import retry_policy
from app.core.memory_store import memory_store
from app.agents.registry import agent_registry
from app.agents.react_executor import react_executor
from app.auth.auth_manager import auth_manager

logger = logging.getLogger("supervisor")

class SupervisorRouter:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SupervisorRouter, cls).__new__(cls)
            cls._instance.active_states: Dict[str, RunState] = {}
            cls._instance._subscribe()
        return cls._instance

    def _subscribe(self):
        event_bus.subscribe("*", self.handle_domain_event)

    async def handle_domain_event(self, event: DomainEvent) -> None:
        run_id = event.run_id
        state = self.active_states.get(run_id)
        if not state:
            return

        logger.info(f"Supervisor handling event {event.type} for run {run_id}")

        if event.type == "RUN_FAILED":
            state.status = "failed"
            return

        if event.type == "SUITE_EXECUTION_FAILED":
            failure_type = "selector" if event.data and event.data.get("failed_selector") else "execution"
            decision = retry_policy.evaluate(run_id, failure_type, state.active_agent)

            if decision["action"] == "terminate":
                await event_bus.publish(DomainEvent(type="RUN_FAILED", run_id=run_id, error=decision["reason"]))
                return

            if decision["action"] == "switch_agent" and decision.get("suggested_agent"):
                agent_config = agent_registry.get(decision["suggested_agent"])
                if agent_config:
                    state.active_agent = agent_config.type
                    context = {"project_id": state.project_id, "run_id": run_id}
                    await react_executor.execute(agent_config, context, state)
                    return

        agent_config = agent_registry.get_agent_for_event(event.type)
        if agent_config:
            state.active_agent = agent_config.type
            state.iteration += 1
            context = {"project_id": state.project_id, "run_id": run_id}
            decision = await react_executor.execute(agent_config, context, state)

            if decision.completed and decision.confidence >= 0.7:
                state.completed_steps.append(agent_config.type)

    async def execute(
        self,
        project_id: str,
        run_id: str,
        website_url: str,
        repo_url: str
    ) -> Dict[str, Any]:
        logger.info(f"Supervisor starting execution for project={project_id}, run={run_id}")

        initial_state = RunState(run_id=run_id, project_id=project_id, status="analyzing")
        self.active_states[run_id] = initial_state

        plan = planner.create_execution_plan(run_id, "Run E2E agentic test suite")
        memory_store.add_memory(run_id, "execution_plan", "generated_test", plan)

        # Pre-authenticate using AuthManager (Fail-Fast Verification)
        try:
            if website_url:
                await auth_manager.get_or_authenticate_session(project_id, website_url, "form")
        except Exception as e:
            logger.error(f"Pre-authentication failed for run {run_id}: {e}")
            initial_state.status = "failed"
            return {"status": "failed", "error": str(e)}

        await event_bus.publish(DomainEvent(type="RUN_STARTED", run_id=run_id, project_id=project_id))
        return {"status": initial_state.status}

supervisor = SupervisorRouter()
