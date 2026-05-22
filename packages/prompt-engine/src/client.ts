import Groq from "groq-sdk";
import { createLogger, RateLimitError } from "@testpilot/shared";
import { getCache, setCache } from "./cache.js";
import crypto from "node:crypto";

const logger = createLogger("prompt-engine");

// Groq free tier: 30 req/min, 14,400 req/day for llama models
const RATE_LIMIT_WINDOW_MS = 60_000;
const MAX_REQUESTS_PER_WINDOW = 28; // leave buffer
let requestTimestamps: number[] = [];

let _client: Groq | null = null;

function getClient(): Groq {
  if (_client) return _client;
  const apiKey = process.env["GROQ_API_KEY"];
  if (!apiKey) throw new Error("GROQ_API_KEY is required");
  _client = new Groq({ apiKey });
  return _client;
}

/** Check rate limit and wait if needed */
async function checkRateLimit(): Promise<void> {
  const now = Date.now();
  requestTimestamps = requestTimestamps.filter((t) => now - t < RATE_LIMIT_WINDOW_MS);

  if (requestTimestamps.length >= MAX_REQUESTS_PER_WINDOW) {
    const oldestInWindow = requestTimestamps[0]!;
    const waitMs = RATE_LIMIT_WINDOW_MS - (now - oldestInWindow) + 100;
    logger.warn({ waitMs }, "Rate limit approaching, waiting");
    await new Promise((resolve) => setTimeout(resolve, waitMs));
  }

  requestTimestamps.push(Date.now());
}

/** Hash prompt for caching */
function hashPrompt(model: string, messages: GroqMessage[]): string {
  const content = JSON.stringify({ model, messages });
  return crypto.createHash("sha256").update(content).digest("hex").slice(0, 16);
}

export interface GroqMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface CompletionOptions {
  model?: string;
  temperature?: number;
  maxTokens?: number;
  jsonMode?: boolean;
  cacheKey?: string; // override auto-cache key
  skipCache?: boolean;
}

export interface CompletionResult {
  content: string;
  model: string;
  inputTokens: number;
  outputTokens: number;
  cached: boolean;
  durationMs: number;
}

/** Send a completion request to Groq with rate limiting and caching */
export async function complete(
  messages: GroqMessage[],
  opts: CompletionOptions = {}
): Promise<CompletionResult> {
  const model = opts.model || process.env["GROQ_MODEL"] || "llama-3.1-8b-instant";
  const cacheKey = opts.cacheKey || hashPrompt(model, messages);
  const start = Date.now();

  // Check cache first
  if (!opts.skipCache) {
    const cached = await getCache(cacheKey);
    if (cached) {
      logger.debug({ cacheKey }, "Cache hit");
      return { ...cached, cached: true, durationMs: Date.now() - start };
    }
  }

  let attempt = 0;
  const maxRetries = 3;
  let backoffMs = 2000;

  while (true) {
    try {
      await checkRateLimit();
      const client = getClient();

      const response = await client.chat.completions.create({
        model,
        messages,
        temperature: opts.temperature ?? 0.1,
        max_tokens: opts.maxTokens ?? 4096,
        ...(opts.jsonMode ? { response_format: { type: "json_object" } } : {}),
      });

      const choice = response.choices[0];
      if (!choice?.message?.content) {
        throw new Error("Empty response from Groq");
      }

      const result: CompletionResult = {
        content: choice.message.content,
        model,
        inputTokens: response.usage?.prompt_tokens ?? 0,
        outputTokens: response.usage?.completion_tokens ?? 0,
        cached: false,
        durationMs: Date.now() - start,
      };

      // Cache the result (1 hour TTL)
      await setCache(cacheKey, result, 3600);

      logger.info(
        { model, inputTokens: result.inputTokens, outputTokens: result.outputTokens, durationMs: result.durationMs },
        "Completion success"
      );

      return result;
    } catch (error: any) {
      const isRateLimit =
        (error instanceof Error && error.message?.toLowerCase().includes("rate limit")) ||
        (error && typeof error === "object" && "status" in error && error.status === 429);

      if (isRateLimit && attempt < maxRetries) {
        attempt++;
        let suggestedWait = 0;
        if (error.retryAfterMs) {
          suggestedWait = error.retryAfterMs;
        } else if (error.headers && error.headers["retry-after"]) {
          const parsed = parseInt(error.headers["retry-after"], 10);
          if (!isNaN(parsed)) {
            suggestedWait = parsed * 1000;
          }
        }
        const waitTime = suggestedWait > 0 ? suggestedWait + 1000 : backoffMs;

        logger.warn({ attempt, waitTime, model, errMsg: error.message }, "Groq rate limit reached, waiting to retry");
        await new Promise((resolve) => setTimeout(resolve, waitTime));
        backoffMs *= 2;
        continue;
      }

      if (isRateLimit) {
        throw new RateLimitError(60_000);
      }
      throw error;
    }
  }
}

/** Parse JSON from AI response, with fallback extraction */
export function parseJsonResponse<T>(content: string): T {
  // Try direct parse
  try {
    return JSON.parse(content) as T;
  } catch {
    // Try extracting from markdown code block
    const jsonMatch = content.match(/```(?:json)?\s*\n?([\s\S]*?)\n?\s*```/);
    if (jsonMatch?.[1]) {
      return JSON.parse(jsonMatch[1]) as T;
    }
    throw new Error(`Failed to parse JSON from AI response: ${content.slice(0, 200)}...`);
  }
}
