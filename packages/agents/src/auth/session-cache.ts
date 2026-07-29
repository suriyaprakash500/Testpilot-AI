import type { AuthSession } from "@testpilot/types";
import { createLogger } from "@testpilot/shared";

const logger = createLogger("session-cache");

/**
 * AuthSessionCache: In-memory session store with TTL expiry checks.
 * Prevents unnecessary re-authentication on consecutive test runs.
 */
export class AuthSessionCache {
  private static instance: AuthSessionCache;
  private cache: Map<string, AuthSession> = new Map();

  private constructor() {}

  public static getInstance(): AuthSessionCache {
    if (!AuthSessionCache.instance) {
      AuthSessionCache.instance = new AuthSessionCache();
    }
    return AuthSessionCache.instance;
  }

  /** Store an authenticated session in cache */
  public set(session: AuthSession): void {
    this.cache.set(session.projectId, session);
    logger.info({ projectId: session.projectId, expiresAt: session.expiresAt }, "AuthSession cached");
  }

  /** Retrieve valid, unexpired session for a project */
  public get(projectId: string): AuthSession | null {
    const session = this.cache.get(projectId);
    if (!session) return null;

    // Check if session has expired
    if (new Date() >= session.expiresAt) {
      logger.info({ projectId }, "Cached AuthSession expired. Evicting from cache.");
      this.cache.delete(projectId);
      return null;
    }

    logger.info({ projectId }, "Valid AuthSession retrieved from cache");
    return session;
  }

  /** Invalidate session for a project */
  public invalidate(projectId: string): void {
    this.cache.delete(projectId);
    logger.info({ projectId }, "AuthSession invalidated");
  }
}

export const authSessionCache = AuthSessionCache.getInstance();
