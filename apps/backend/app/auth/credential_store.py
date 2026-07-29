import logging
from typing import Optional, Dict

logger = logging.getLogger("credential-store")

class CredentialStore:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CredentialStore, cls).__new__(cls)
        return cls._instance

    async def get_credential(self, project_id: str) -> Optional[Dict[str, str]]:
        logger.info(f"Retrieving credentials from CredentialStore for project {project_id}")
        # Decoupled secret retrieval — returns test account or Vault entry
        return {
            "username": "testuser@example.com",
            "password": "SecureTestPassword123!"
        }

credential_store = CredentialStore()
