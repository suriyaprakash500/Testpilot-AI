import type { AuthStrategy, AuthStrategyContext } from "./base-strategy.js";
import type { AuthSession } from "@testpilot/types";
import { createLogger } from "@testpilot/shared";

const logger = createLogger("header-auth-strategy");

/** API Key / Bearer Header Authentication Strategy */
export class HeaderAuthStrategy implements AuthStrategy {
  public readonly type = "header" as const;

  async authenticate(context: AuthStrategyContext): Promise<AuthSession> {
    logger.info({ projectId: context.projectId }, "Executing HeaderAuthStrategy");

    const token = context.credential?.secretToken || (context.customParams?.["token"] as string);
    const headers = { Authorization: `Bearer ${token}` };
    const expiresAt = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000); // 7 days TTL

    return {
      id: crypto.randomUUID(),
      projectId: context.projectId,
      strategy: this.type,
      headers,
      createdAt: new Date(),
      expiresAt,
    };
  }
}
