import { EventEmitter } from "eventemitter3";
import type { DomainEvent } from "@testpilot/types";
import { createLogger } from "@testpilot/shared";

const logger = createLogger("event-bus");

type EventListener = (event: DomainEvent) => void | Promise<void>;

/**
 * Message Bus Abstraction for System Domain Events.
 * Decouples agents, supervisors, and triggers from persistent messaging implementations.
 * Currently uses EventEmitter (pluggable to NATS/Redis Streams/Kafka in enterprise production).
 */
export class EventBus {
  private static instance: EventBus;
  private emitter = new EventEmitter();

  private constructor() {}

  public static getInstance(): EventBus {
    if (!EventBus.instance) {
      EventBus.instance = new EventBus();
    }
    return EventBus.instance;
  }

  /** Publish a domain event to the bus */
  public publish(event: DomainEvent): void {
    logger.info({ eventType: event.type, runId: (event as any).runId }, "Publishing domain event");
    this.emitter.emit(event.type, event);
    this.emitter.emit("*", event);
  }

  /** Subscribe to a specific domain event type */
  public subscribe(eventType: DomainEvent["type"] | "*", listener: EventListener): void {
    this.emitter.on(eventType, async (event: DomainEvent) => {
      try {
        await listener(event);
      } catch (err) {
        logger.error({ eventType: event.type, err }, "Error handling domain event in subscriber");
      }
    });
  }

  /** Clear subscribers */
  public unsubscribeAll(): void {
    this.emitter.removeAllListeners();
  }
}

export const eventBus = EventBus.getInstance();
