import type { AuthStrategy, AuthStrategyContext } from "./base-strategy.js";
import type { AuthSession } from "@testpilot/types";
import { createLogger } from "@testpilot/shared";

const logger = createLogger("cookie-auth-strategy");

/** Direct Session Cookie Authentication Strategy */
export class CookieAuthStrategy implements AuthStrategy {
  public readonly type = "cookie" as const;

  async authenticate(context: AuthStrategyContext): Promise<AuthSession> {
    logger.info({ projectId: context.projectId }, "Executing CookieAuthStrategy");

    const rawCookies = (context.customParams?.["cookies"] as Array<Record<string, unknown>>) || [];
    const expiresAt = new Date(Date.now() + 12 * 60 * 60 * 1000); // 12 hours TTL

    return {
      id: crypto.randomUUID(),
      projectId: context.projectId,
      strategy: this.type,
      cookies: rawCookies,
      createdAt: new Date(),
      expiresAt,
    };
  }
}
