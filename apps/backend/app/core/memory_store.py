import uuid
from typing import Dict, List, Any
from app.models import MemoryItem

class MemoryStore:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MemoryStore, cls).__new__(cls)
            cls._instance.items: Dict[str, List[MemoryItem]] = {}
        return cls._instance

    def add_memory(self, run_id: str, key: str, memory_type: str, content: Any) -> MemoryItem:
        item = MemoryItem(
            id=str(uuid.uuid4()),
            run_id=run_id,
            key=key,
            type=memory_type,
            content=content
        )
        if run_id not in self.items:
            self.items[run_id] = []
        self.items[run_id].append(item)
        return item

    def get_memories(self, run_id: str) -> List[MemoryItem]:
        return self.items.get(run_id, [])

    def clear_run_memory(self, run_id: str) -> None:
        self.items.pop(run_id, None)

memory_store = MemoryStore()
