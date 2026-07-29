import type { MemoryItem } from "@testpilot/types";
import { createLogger } from "@testpilot/shared";

const logger = createLogger("memory-store");

/**
 * Dedicated Memory Store for tracking run history, failure snapshots,
 * and attempted fixes to prevent duplicate unsuccessful loops.
 */
export class MemoryStore {
  private static instance: MemoryStore;
  private items: Map<string, MemoryItem[]> = new Map();

  private constructor() {}

  public static getInstance(): MemoryStore {
    if (!MemoryStore.instance) {
      MemoryStore.instance = new MemoryStore();
    }
    return MemoryStore.instance;
  }

  /** Add a memory entry for a given test run */
  public addMemory(
    runId: string,
    key: string,
    type: MemoryItem["type"],
    content: unknown
  ): MemoryItem {
    const runMemories = this.items.get(runId) || [];
    const newItem: MemoryItem = {
      id: crypto.randomUUID(),
      runId,
      key,
      type,
      content,
      timestamp: new Date(),
    };

    runMemories.push(newItem);
    this.items.set(runId, runMemories);
    logger.debug({ runId, key, type }, "Memory entry stored");
    return newItem;
  }

  /** Retrieve all memories for a run */
  public getMemories(runId: string): MemoryItem[] {
    return this.items.get(runId) || [];
  }

  /** Filter memories by type */
  public getMemoriesByType(runId: string, type: MemoryItem["type"]): MemoryItem[] {
    return this.getMemories(runId).filter((item) => item.type === type);
  }

  /** Check if a specific fix attempt was already tried */
  public hasAttemptedFix(runId: string, fixKey: string): boolean {
    const attempted = this.getMemoriesByType(runId, "attempted_fix");
    return attempted.some((item) => item.key === fixKey);
  }

  /** Clear memory cache for a completed run */
  public clearRunMemory(runId: string): void {
    this.items.delete(runId);
  }
}

export const memoryStore = MemoryStore.getInstance();
