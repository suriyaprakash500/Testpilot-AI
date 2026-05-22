import { z } from "zod";

const configSchema = z.object({
  // Database
  DATABASE_URL: z.string().url(),

  // Redis
  REDIS_URL: z.string().url(),

  // AI
  GROQ_API_KEY: z.string().min(1),

  // GitHub OAuth
  GITHUB_CLIENT_ID: z.string().min(1),
  GITHUB_CLIENT_SECRET: z.string().min(1),

  // Auth
  JWT_SECRET: z.string().min(32),

  // Server
  BACKEND_PORT: z.coerce.number().default(3001),
  BACKEND_URL: z.string().url().default("http://localhost:3001"),
  FRONTEND_URL: z.string().url().default("http://localhost:3000"),

  // Storage
  ARTIFACTS_DIR: z.string().default("./artifacts"),
  REPOS_DIR: z.string().default("./repos"),

  // Environment
  NODE_ENV: z.enum(["development", "production", "test"]).default("development"),
  LOG_LEVEL: z.enum(["trace", "debug", "info", "warn", "error", "fatal"]).default("info"),
});

export type Config = z.infer<typeof configSchema>;

let _config: Config | null = null;

/** Load and validate environment config. Throws on invalid config. */
export function loadConfig(): Config {
  if (_config) return _config;

  const result = configSchema.safeParse(process.env);
  if (!result.success) {
    const missing = result.error.issues
      .map((i) => `  ${i.path.join(".")}: ${i.message}`)
      .join("\n");
    throw new Error(`Invalid configuration:\n${missing}`);
  }

  _config = result.data;
  return _config;
}

/** Get config (must call loadConfig first) */
export function getConfig(): Config {
  if (!_config) throw new Error("Config not loaded. Call loadConfig() first.");
  return _config;
}
