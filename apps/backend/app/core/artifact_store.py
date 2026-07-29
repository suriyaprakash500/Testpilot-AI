import os
import uuid
import logging
from typing import Dict, List, Any
from app.config import settings

logger = logging.getLogger("artifact-store")

class ArtifactStore:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ArtifactStore, cls).__new__(cls)
            cls._instance.artifacts: Dict[str, List[Dict[str, Any]]] = {}
        return cls._instance

    async def store_artifact(
        self,
        run_id: str,
        artifact_type: str,
        filename: str,
        content: bytes | str
    ) -> Dict[str, Any]:
        os.makedirs(settings.artifacts_dir, exist_ok=True)
        file_path = os.path.join(settings.artifacts_dir, f"{run_id}-{filename}")

        if isinstance(content, str):
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        else:
            with open(file_path, "wb") as f:
                f.write(content)

        ref = {
            "id": str(uuid.uuid4()),
            "run_id": run_id,
            "type": artifact_type,
            "file_path": file_path,
            "size_bytes": os.path.getsize(file_path)
        }

        if run_id not in self.artifacts:
            self.artifacts[run_id] = []
        self.artifacts[run_id].append(ref)
        logger.info(f"Stored artifact {filename} ({artifact_type}) for run {run_id}")
        return ref

artifact_store = ArtifactStore()
