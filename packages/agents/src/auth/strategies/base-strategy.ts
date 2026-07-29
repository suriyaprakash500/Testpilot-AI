import type { AuthSession, AuthStrategyType } from "@testpilot/types";
import type { DecryptedCredential } from "../credential-store.js";

export interface AuthStrategyContext {
  projectId: string;
  websiteUrl: string;
  credential?: DecryptedCredential | null;
  customParams?: Record<string, unknown>;
}

/**
 * Base Strategy Interface for Authentication Implementations.
 * (FormAuth, OAuth, CookieAuth, HeaderAuth, APIKeyAuth)
 */
export interface AuthStrategy {
  readonly type: AuthStrategyType;
  authenticate(context: AuthStrategyContext): Promise<AuthSession>;
}
