import { drizzle } from "drizzle-orm/node-postgres";
import pg from "pg";
import * as schema from "./schema.js";
import { createLogger } from "@testpilot/shared";

const logger = createLogger("database");

let _pool: pg.Pool | null = null;
let _db: ReturnType<typeof drizzle<typeof schema>> | null = null;

/** Initialize database connection pool and return Drizzle client */
export function getDb(databaseUrl?: string) {
  if (_db) return _db;

  const url = databaseUrl || process.env["DATABASE_URL"];
  if (!url) throw new Error("DATABASE_URL is required");

  _pool = new pg.Pool({
    connectionString: url,
    max: 20,
    idleTimeoutMillis: 30_000,
    connectionTimeoutMillis: 5_000,
  });

  _pool.on("error", (err) => {
    logger.error({ err }, "Unexpected database pool error");
  });

  _db = drizzle(_pool, { schema });
  logger.info("Database connection pool initialized");
  return _db;
}

/** Gracefully close database connection pool */
export async function closeDb() {
  if (_pool) {
    await _pool.end();
    _pool = null;
    _db = null;
    logger.info("Database connection pool closed");
  }
}

export type Database = ReturnType<typeof getDb>;
