import logging
from typing import Optional, Dict

logger = logging.getLogger("credential-store")

class CredentialStore:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CredentialStore, cls).__new__(cls)
            cls._instance.store: Dict[str, Dict[str, str]] = {}
        return cls._instance

    async def set_credential(self, project_id: str, username: str, password: str) -> None:
        """Stores credentials for a project."""
        logger.info(f"Saving credentials in CredentialStore for project {project_id}")
        self.store[project_id] = {
            "username": username,
            "password": password
        }

    async def get_credential(self, project_id: str) -> Optional[Dict[str, str]]:
        """Retrieves stored credentials for a project, falling back to default test credentials."""
        logger.info(f"Retrieving credentials from CredentialStore for project {project_id}")
        if project_id in self.store:
            return self.store[project_id]

        return {
            "username": "testuser@example.com",
            "password": "SecureTestPassword123!"
        }

credential_store = CredentialStore()
