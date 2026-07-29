import logging
from typing import Dict, Optional
from datetime import datetime
from app.models import AuthSession

logger = logging.getLogger("session-cache")

class AuthSessionCache:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AuthSessionCache, cls).__new__(cls)
            cls._instance.cache: Dict[str, AuthSession] = {}
        return cls._instance

    def set(self, session: AuthSession) -> None:
        self.cache[session.project_id] = session
        logger.info(f"AuthSession cached for project {session.project_id}, expires at {session.expires_at}")

    def get(self, project_id: str) -> Optional[AuthSession]:
        session = self.cache.get(project_id)
        if not session:
            return None

        if datetime.utcnow() >= session.expires_at:
            logger.info(f"Cached AuthSession for project {project_id} expired. Evicting.")
            self.cache.pop(project_id, None)
            return None

        logger.info(f"Valid AuthSession retrieved from cache for project {project_id}")
        return session

    def invalidate(self, project_id: str) -> None:
        self.cache.pop(project_id, None)
        logger.info(f"AuthSession invalidated for project {project_id}")

auth_session_cache = AuthSessionCache()
