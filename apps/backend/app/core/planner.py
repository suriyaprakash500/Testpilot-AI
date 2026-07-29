import uuid
import logging
from typing import Dict, Any, List

logger = logging.getLogger("planner")

class Planner:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Planner, cls).__new__(cls)
        return cls._instance

    def create_execution_plan(self, run_id: str, goal: str) -> Dict[str, Any]:
        logger.info(f"Decomposing task goal for run={run_id}")
        tasks = [
            {"id": "task-1", "target_agent": "repo-analysis", "trigger": "RUN_STARTED"},
            {"id": "task-2", "target_agent": "test-planning", "trigger": "REPO_ANALYZED"},
            {"id": "task-3", "target_agent": "playwright-gen", "trigger": "PLAN_COMPLETED"},
            {"id": "task-4", "target_agent": "browser-execution", "trigger": "CODE_GENERATED"},
            {"id": "task-5", "target_agent": "failure-analysis", "trigger": "SUITE_EXECUTION_FAILED"},
            {"id": "task-6", "target_agent": "github-integration", "trigger": "SUITE_EXECUTION_PASSED"}
        ]
        return {
            "id": str(uuid.uuid4()),
            "run_id": run_id,
            "goal": goal,
            "tasks": tasks
        }

planner = Planner()
