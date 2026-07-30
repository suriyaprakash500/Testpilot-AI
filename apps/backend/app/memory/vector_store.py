import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("vector-memory")

class PersistentMemory:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(PersistentMemory, cls).__new__(cls)
            cls._instance.client = None
            cls._instance.collection = None
            cls._instance.fallback_store: List[Dict[str, Any]] = []

            try:
                import chromadb
                cls._instance.client = chromadb.PersistentClient(path="./data/chromadb")
                cls._instance.collection = cls._instance.client.get_or_create_collection("testpilot_memory")
                logger.info("ChromaDB persistent memory initialized at ./data/chromadb")
            except ImportError:
                logger.warning("chromadb package not installed. Using in-memory persistent vector memory fallback.")
            except Exception as e:
                logger.error(f"Failed to initialize ChromaDB: {e}. Using fallback.")

        return cls._instance

    def store(self, project_id: str, memory_id: str, learning_type: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Store a failure pattern, healed selector, or application quirk."""
        meta = metadata or {}
        meta["project_id"] = project_id
        meta["learning_type"] = learning_type

        if self.collection:
            try:
                self.collection.add(
                    documents=[content],
                    metadatas=[meta],
                    ids=[f"{project_id}_{memory_id}"]
                )
                logger.info(f"Stored learning memory in ChromaDB: {memory_id} for project {project_id}")
                return
            except Exception as e:
                logger.error(f"Error storing memory {memory_id} in ChromaDB: {e}")

        # Fallback in-memory storage
        self.fallback_store.append({
            "id": memory_id,
            "project_id": project_id,
            "content": content,
            "metadata": meta
        })
        logger.info(f"Stored learning memory in fallback store: {memory_id} for project {project_id}")

    def search(self, query: str, project_id: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search past learnings by similarity or keyword matching."""
        if self.collection:
            try:
                results = self.collection.query(
                    query_texts=[query],
                    n_results=top_k,
                    where={"project_id": project_id}
                )

                learnings = []
                if results and results.get("documents") and results["documents"][0]:
                    docs = results["documents"][0]
                    metas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(docs)
                    for doc, meta in zip(docs, metas):
                        learnings.append({
                            "content": doc,
                            "metadata": meta
                        })
                return learnings
            except Exception as e:
                logger.error(f"Error searching ChromaDB memory: {e}")

        # Fallback keyword match search
        matches = []
        query_words = set(query.lower().split())
        for item in self.fallback_store:
            if item.get("project_id") == project_id:
                content_lower = item["content"].lower()
                if any(w in content_lower for w in query_words):
                    matches.append({
                        "content": item["content"],
                        "metadata": item["metadata"]
                    })
        return matches[:top_k]

persistent_memory = PersistentMemory()
