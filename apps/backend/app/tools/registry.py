import logging
from typing import Dict, Optional, List
from app.models import ToolDefinition

logger = logging.getLogger("tool-registry")

class ToolRegistry:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ToolRegistry, cls).__new__(cls)
            cls._instance.tools: Dict[str, ToolDefinition] = {}
        return cls._instance

    def register(self, tool: ToolDefinition) -> None:
        self.tools[tool.name] = tool
        logger.debug(f"Registered tool metadata: {tool.name}")

    def get(self, name: str) -> Optional[ToolDefinition]:
        return self.tools.get(name)

    def get_subset(self, names: List[str]) -> List[ToolDefinition]:
        return [self.tools[name] for name in names if name in self.tools]

tool_registry = ToolRegistry()

# Register built-in tool metadata definitions
tool_registry.register(ToolDefinition(
    name="analyze_repo_structure",
    description="Clones and analyzes repository structure, identifying framework, routes, and components.",
    handler_key="handler:repo:analyze",
    parameters={"type": "object", "properties": {"repo_url": {"type": "string"}}, "required": ["repo_url"]}
))

tool_registry.register(ToolDefinition(
    name="inspect_dom_nodes",
    description="Launches Playwright browser to scan page and extract interactive DOM elements.",
    handler_key="handler:browser:inspect-dom",
    parameters={"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}
))

tool_registry.register(ToolDefinition(
    name="run_playwright_suite",
    description="Executes a Playwright test script in a headless browser sandbox.",
    handler_key="handler:browser:run-suite",
    parameters={"type": "object", "properties": {"test_code": {"type": "string"}, "test_name": {"type": "string"}}, "required": ["test_code", "test_name"]}
))

tool_registry.register(ToolDefinition(
    name="repair_locator",
    description="Analyzes stack trace and repairs broken test locators.",
    handler_key="handler:healing:repair-locator",
    parameters={"type": "object", "properties": {"failed_selector": {"type": "string"}, "error_message": {"type": "string"}}, "required": ["failed_selector", "error_message"]}
))

tool_registry.register(ToolDefinition(
    name="authenticate_session",
    description="Authenticates session using configured credentials or cached AuthSession.",
    handler_key="handler:auth:session",
    parameters={"type": "object", "properties": {"project_id": {"type": "string"}, "website_url": {"type": "string"}}, "required": ["project_id", "website_url"]}
))
