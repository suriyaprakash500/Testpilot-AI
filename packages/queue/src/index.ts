import { Queue, Worker, type Job, type WorkerOptions, type QueueOptions } from "bullmq";
import IORedis from "ioredis";
import { createLogger } from "@testpilot/shared";
import type { AgentType } from "@testpilot/types";

const logger = createLogger("queue");

// ============================================================
// Redis Connection
// ============================================================

let _redis: IORedis | null = null;

export function getRedis(url?: string): IORedis {
  if (_redis) return _redis;
  const redisUrl = url || process.env["REDIS_URL"] || "redis://localhost:6379";
  _redis = new IORedis(redisUrl, { maxRetriesPerRequest: null });
  _redis.on("error", (err) => logger.error({ err }, "Redis connection error"));
  _redis.on("connect", () => logger.info("Redis connected"));
  return _redis;
}

export async function closeRedis() {
  if (_redis) {
    await _redis.quit();
    _redis = null;
  }
}

// ============================================================
// Queue Definitions
// ============================================================

export const QUEUE_NAMES = {
  REPO_ANALYSIS: "repo-analysis",
  TEST_PLANNING: "test-planning",
  TEST_GENERATION: "test-generation",
  TEST_EXECUTION: "test-execution",
  FAILURE_ANALYSIS: "failure-analysis",
  GITHUB_SYNC: "github-sync",
} as const;

export type QueueName = (typeof QUEUE_NAMES)[keyof typeof QUEUE_NAMES];

/** Job payload types for each queue */
export interface QueuePayloads {
  "repo-analysis": { projectId: string; runId: string; repoUrl: string; githubToken: string };
  "test-planning": { projectId: string; runId: string };
  "test-generation": { projectId: string; runId: string; scenarioId: string };
  "test-execution": { projectId: string; runId: string; testCaseId: string };
  "failure-analysis": { projectId: string; runId: string; testCaseId: string };
  "github-sync": { projectId: string; runId: string; action: "comment" | "issue" | "commit" };
}

const queues = new Map<string, Queue>();

/** Get or create a typed BullMQ queue */
export function getQueue<T extends QueueName>(name: T): Queue<QueuePayloads[T]> {
  if (queues.has(name)) return queues.get(name)! as Queue<QueuePayloads[T]>;

  const connection = getRedis();
  const queue = new Queue<QueuePayloads[T]>(name, {
    connection,
    defaultJobOptions: {
      attempts: 3,
      backoff: { type: "exponential", delay: 2000 },
      removeOnComplete: { count: 100 },
      removeOnFail: { count: 50 },
    },
  });

  queues.set(name, queue as Queue);
  logger.info({ queue: name }, "Queue created");
  return queue;
}

// ============================================================
// Worker Factory
// ============================================================

const workers = new Map<string, Worker>();

/** Create a typed BullMQ worker for a queue */
export function createWorker<T extends QueueName>(
  name: T,
  processor: (job: Job<QueuePayloads[T]>) => Promise<void>,
  opts?: Partial<WorkerOptions>
): Worker<QueuePayloads[T]> {
  const connection = getRedis();
  const worker = new Worker<QueuePayloads[T]>(name, processor, {
    connection,
    concurrency: 1,
    ...opts,
  });

  worker.on("completed", (job) => {
    logger.info({ queue: name, jobId: job.id }, "Job completed");
  });
  worker.on("failed", (job, err) => {
    logger.error({ queue: name, jobId: job?.id, err }, "Job failed");
  });

  workers.set(name, worker as Worker);
  logger.info({ queue: name }, "Worker started");
  return worker;
}

/** Add a job to a queue */
export async function enqueue<T extends QueueName>(
  name: T,
  data: QueuePayloads[T],
  opts?: { priority?: number; delay?: number }
) {
  const queue = getQueue(name) as any;
  const job = await queue.add(name, data, opts);
  logger.info({ queue: name, jobId: job.id }, "Job enqueued");
  return job;
}

/** Gracefully shut down all queues and workers */
export async function closeQueues() {
  for (const [name, worker] of workers) {
    await worker.close();
    logger.info({ queue: name }, "Worker closed");
  }
  for (const [name, queue] of queues) {
    await queue.close();
    logger.info({ queue: name }, "Queue closed");
  }
  workers.clear();
  queues.clear();
  await closeRedis();
}
