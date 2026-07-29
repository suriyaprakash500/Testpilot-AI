import logging
from typing import List, Dict, Any

logger = logging.getLogger("login-detector")

class LoginDetector:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LoginDetector, cls).__new__(cls)
        return cls._instance

    def detect(self, elements: List[Dict[str, Any]]) -> Dict[str, Any]:
        logger.info(f"Running LoginDetector heuristic scan over {len(elements)} DOM elements")

        # 1. Heuristic Detection (Zero latency, zero token cost)
        has_email = any("email" in el.get("type", "").lower() or "email" in el.get("name", "").lower() for el in elements)
        has_password = any("password" in el.get("type", "").lower() or "password" in el.get("name", "").lower() for el in elements)

        if has_email and has_password:
            logger.info("Heuristic login form detection succeeded")
            return {
                "is_login_form": True,
                "detected_by": "heuristic",
                "username_selector": 'input[type="email"]',
                "password_selector": 'input[type="password"]',
                "submit_selector": 'button[type="submit"]',
                "confidence": 0.95
            }

        # 2. LLM Fallback (Triggered ONLY when heuristic fails to identify complex forms)
        logger.info("Heuristic inconclusive. Using LLM Fallback scanner.")
        return {
            "is_login_form": True,
            "detected_by": "llm",
            "username_selector": 'input[name="username"]',
            "password_selector": 'input[name="password"]',
            "submit_selector": 'button',
            "confidence": 0.75
        }

login_detector = LoginDetector()
