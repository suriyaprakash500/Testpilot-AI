import "./env.js";
import pino from "pino";

const level = process.env["LOG_LEVEL"] || "info";

/** Root logger instance — use createLogger() for child loggers with context */
export const rootLogger = pino({
  level,
  transport:
    process.env["NODE_ENV"] !== "production"
      ? { target: "pino/file", options: { destination: 1 } } // stdout pretty in dev
      : undefined,
  formatters: {
    level(label) {
      return { level: label };
    },
  },
  timestamp: pino.stdTimeFunctions.isoTime,
});

/** Create a child logger with component context */
export function createLogger(component: string, meta?: Record<string, unknown>) {
  return rootLogger.child({ component, ...meta });
}

export type Logger = pino.Logger;
