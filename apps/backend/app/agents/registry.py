import logging
from typing import Dict, Optional, List
from app.models import AgentDefinitionConfig, AgentType

logger = logging.getLogger("agent-registry")

class AgentRegistry:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AgentRegistry, cls).__new__(cls)
            cls._instance.agents: Dict[AgentType, AgentDefinitionConfig] = {}
        return cls._instance

    def register(self, config: AgentDefinitionConfig) -> None:
        self.agents[config.type] = config
        logger.info(f"Registered capability config for agent: {config.name} ({config.type})")

    def get(self, agent_type: AgentType) -> Optional[AgentDefinitionConfig]:
        return self.agents.get(agent_type)

    def get_agent_for_event(self, event_type: str) -> Optional[AgentDefinitionConfig]:
        candidates = [a for a in self.agents.values() if event_type in a.supported_events]
        if not candidates:
            return None
        candidates.sort(key=lambda a: a.priority, reverse=True)
        return candidates[0]

agent_registry = AgentRegistry()

# Register agent configurations
agent_registry.register(AgentDefinitionConfig(
    name="Repo Analysis Agent",
    type="repo-analysis",
    description="Parses repository structure, routes, and frameworks.",
    system_prompt="Analyze code structure and frameworks.",
    allowed_tools=["analyze_repo_structure"],
    supported_events=["RUN_STARTED"],
    priority=10
))

agent_registry.register(AgentDefinitionConfig(
    name="Test Planning Agent",
    type="test-planning",
    description="Derives E2E user flows and assertions.",
    system_prompt="Plan resilient test scenarios.",
    allowed_tools=["inspect_dom_nodes"],
    supported_events=["REPO_ANALYZED"],
    priority=10
))

agent_registry.register(AgentDefinitionConfig(
    name="Playwright Code Generator",
    type="playwright-gen",
    description="Generates Playwright test code.",
    system_prompt="Generate clean Playwright test code.",
    allowed_tools=["inspect_dom_nodes"],
    supported_events=["PLAN_COMPLETED"],
    priority=10
))

agent_registry.register(AgentDefinitionConfig(
    name="Browser Execution Agent",
    type="browser-execution",
    description="Executes tests in Playwright browser with active AuthSession.",
    system_prompt="Run Playwright suites using active AuthSessions.",
    allowed_tools=["run_playwright_suite", "authenticate_session"],
    supported_events=["CODE_GENERATED", "LOCATOR_FIXED"],
    priority=10
))

agent_registry.register(AgentDefinitionConfig(
    name="Failure Analysis Agent",
    type="failure-analysis",
    description="Diagnoses stack traces and auto-heals locators.",
    system_prompt="Diagnose root cause and repair broken selectors.",
    allowed_tools=["repair_locator"],
    supported_events=["SUITE_EXECUTION_FAILED"],
    priority=15
))
