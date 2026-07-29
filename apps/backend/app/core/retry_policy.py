import math
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("retry-policy")

class RetryPolicy:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RetryPolicy, cls).__new__(cls)
            cls._instance.attempts: Dict[str, int] = {}
        return cls._instance

    def evaluate(
        self,
        run_id: str,
        failure_type: str,
        current_agent: Optional[str] = None,
        max_retries: int = 3
    ) -> Dict[str, Any]:
        key = f"{run_id}:{failure_type}"
        count = self.attempts.get(key, 0) + 1
        self.attempts[key] = count

        logger.info(f"Evaluating failure retry policy for run={run_id}, attempts={count}")

        if count > max_retries:
            return {
                "action": "terminate",
                "delay_ms": 0,
                "reason": f"Exceeded maximum retries ({max_retries}) for failure type '{failure_type}'"
            }

        if failure_type == "selector" and current_agent == "browser-execution":
            return {
                "action": "switch_agent",
                "delay_ms": 500,
                "suggested_agent": "failure-analysis",
                "reason": "Locator failure detected. Switching to Failure Diagnostics Agent."
            }

        delay_ms = int(math.pow(2, count) * 1000)
        return {
            "action": "exponential_backoff",
            "delay_ms": delay_ms,
            "reason": f"Retrying after {delay_ms}ms backoff (Attempt {count}/{max_retries})"
        }

retry_policy = RetryPolicy()
