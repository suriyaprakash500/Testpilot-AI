import asyncio
import logging
from typing import Callable, Awaitable, List, Dict
from app.models import DomainEvent

logger = logging.getLogger("event-bus")

EventListener = Callable[[DomainEvent], Awaitable[None]]

class EventBus:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance.subscribers: Dict[str, List[EventListener]] = {}
        return cls._instance

    def subscribe(self, event_type: str, listener: EventListener) -> None:
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(listener)

    async def publish(self, event: DomainEvent) -> None:
        logger.info(f"Publishing domain event: {event.type} for run {event.run_id}")
        listeners = self.subscribers.get(event.type, []) + self.subscribers.get("*", [])
        for listener in listeners:
            try:
                asyncio.create_task(listener(event))
            except Exception as e:
                logger.error(f"Error executing event listener for {event.type}: {e}")

event_bus = EventBus()
