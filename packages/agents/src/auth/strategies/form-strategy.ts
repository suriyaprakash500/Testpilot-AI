import type { AuthStrategy, AuthStrategyContext } from "./base-strategy.js";
import type { AuthSession } from "@testpilot/types";
import { authenticateAndSaveState } from "@testpilot/playwright-engine";
import { createLogger } from "@testpilot/shared";
import path from "node:path";

const logger = createLogger("form-auth-strategy");

/** Form-based Email/Password Authentication Strategy */
export class FormAuthStrategy implements AuthStrategy {
  public readonly type = "form" as const;

  async authenticate(context: AuthStrategyContext): Promise<AuthSession> {
    logger.info({ projectId: context.projectId, websiteUrl: context.websiteUrl }, "Executing FormAuthStrategy");

    if (!context.credential || !context.credential.username || !context.credential.password) {
      throw new Error("FormAuthStrategy requires non-null username and password credentials");
    }

    const storageDir = path.resolve(process.env["ARTIFACTS_DIR"] || "./artifacts", "auth");
    const storageStatePath = path.join(storageDir, `${context.projectId}-storage-state.json`);

    await authenticateAndSave({
      websiteUrl: context.websiteUrl,
      email: context.credential.username,
      password: context.credential.password,
      storageStatePath,
    });

    const expiresAt = new Date(Date.now() + 24 * 60 * 60 * 1000); // 24 hours TTL
    return {
      id: crypto.randomUUID(),
      projectId: context.projectId,
      strategy: this.type,
      storageStatePath,
      createdAt: new Date(),
      expiresAt,
    };
  }
}
