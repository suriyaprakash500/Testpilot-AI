import uuid
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger("telemetry")

class TelemetryStore:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TelemetryStore, cls).__new__(cls)
            cls._instance.events: List[Dict[str, Any]] = []
        return cls._instance

    def record(
        self,
        run_id: str,
        metric: str,
        value: float,
        agent_type: Optional[str] = None,
        tool_name: Optional[str] = None
    ) -> None:
        event = {
            "id": str(uuid.uuid4()),
            "run_id": run_id,
            "metric": metric,
            "value": value,
            "agent_type": agent_type,
            "tool_name": tool_name,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.events.append(event)
        logger.debug(f"Telemetry recorded: {metric}={value} for agent={agent_type}")

    def get_events_for_run(self, run_id: str) -> List[Dict[str, Any]]:
        return [e for e in self.events if e["run_id"] == run_id]

telemetry = TelemetryStore()
