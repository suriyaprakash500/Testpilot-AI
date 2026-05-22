import IORedis from "ioredis";
import { createLogger } from "@testpilot/shared";
import type { CompletionResult } from "./client.js";

const logger = createLogger("prompt-cache");

let _redis: IORedis | null = null;

function getRedis(): IORedis | null {
  if (_redis) return _redis;
  try {
    const url = process.env["REDIS_URL"];
    if (!url) return null;
    _redis = new IORedis(url, { maxRetriesPerRequest: 3, lazyConnect: true });
    _redis.on("error", (err) => {
      logger.debug({ err }, "Redis connection error (expected when Redis is offline)");
    });
    _redis.connect().catch(() => {
      logger.warn("Redis not available, prompt caching disabled");
      _redis = null;
    });
    return _redis;
  } catch {
    return null;
  }
}

const CACHE_PREFIX = "tp:prompt:";

/** Get cached completion result */
export async function getCache(key: string): Promise<Omit<CompletionResult, "cached" | "durationMs"> | null> {
  const redis = getRedis();
  if (!redis) return null;

  try {
    const data = await redis.get(`${CACHE_PREFIX}${key}`);
    return data ? JSON.parse(data) : null;
  } catch (err) {
    logger.warn({ err, key }, "Cache read error");
    return null;
  }
}

/** Set cached completion result */
export async function setCache(
  key: string,
  result: CompletionResult,
  ttlSeconds: number
): Promise<void> {
  const redis = getRedis();
  if (!redis) return;

  try {
    const data = JSON.stringify({
      content: result.content,
      model: result.model,
      inputTokens: result.inputTokens,
      outputTokens: result.outputTokens,
    });
    await redis.setex(`${CACHE_PREFIX}${key}`, ttlSeconds, data);
  } catch (err) {
    logger.warn({ err, key }, "Cache write error");
  }
}
