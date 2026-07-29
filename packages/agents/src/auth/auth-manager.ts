import type { AuthSession, AuthStrategyType } from "@testpilot/types";
import { createLogger } from "@testpilot/shared";
import { credentialStore } from "./credential-store.js";
import { authSessionCache } from "./session-cache.js";
import type { AuthStrategy, AuthStrategyContext } from "./strategies/base-strategy.js";
import { FormAuthStrategy } from "./strategies/form-strategy.js";
import { CookieAuthStrategy } from "./strategies/cookie-strategy.js";
import { HeaderAuthStrategy } from "./strategies/header-strategy.js";
import { chromium } from "playwright";

const logger = createLogger("auth-manager");

/**
 * AuthManager: Enterprise Authentication Orchestrator.
 * Handles secret retrieval, session caching, multi-strategy authentication,
 * and fail-fast post-authentication verification.
 */
export class AuthManager {
  private static instance: AuthManager;
  private strategies: Map<AuthStrategyType, AuthStrategy> = new Map();

  private constructor() {
    this.registerStrategy(new FormAuthStrategy());
    this.registerStrategy(new CookieAuthStrategy());
    this.registerStrategy(new HeaderAuthStrategy());
  }

  public static getInstance(): AuthManager {
    if (!AuthManager.instance) {
      AuthManager.instance = new AuthManager();
    }
    return AuthManager.instance;
  }

  /** Register an authentication strategy implementation */
  public registerStrategy(strategy: AuthStrategy): void {
    this.strategies.set(strategy.type, strategy);
  }

  /**
   * Acquire a valid AuthSession (from cache or via new authentication).
   * Performs fail-fast post-authentication verification to prevent multi-test failure cascades.
   */
  public async getOrAuthenticateSession(
    projectId: string,
    websiteUrl: string,
    strategyType: AuthStrategyType = "form",
    customParams?: Record<string, unknown>
  ): Promise<AuthSession> {
    logger.info({ projectId, websiteUrl, strategyType }, "AuthManager acquiring AuthSession");

    // 1. Check AuthSessionCache
    let session = authSessionCache.get(projectId);
    if (session) {
      logger.info({ projectId }, "Reusing cached valid AuthSession");
      return session;
    }

    // 2. Fetch Credentials from CredentialStore
    const credential = await credentialStore.getCredential(projectId);

    // 3. Resolve Strategy & Authenticate
    const strategy = this.strategies.get(strategyType);
    if (!strategy) {
      throw new Error(`Unsupported authentication strategy type '${strategyType}'`);
    }

    const context: AuthStrategyContext = {
      projectId,
      websiteUrl,
      credential,
      customParams,
    };

    session = await strategy.authenticate(context);

    // 4. Fail-Fast Post-Authentication Verification
    const isValid = await this.verifySessionPostAuth(session, websiteUrl);
    if (!isValid) {
      authSessionCache.invalidate(projectId);
      logger.error({ projectId }, "Post-authentication verification failed. Aborting run.");
      throw new Error("Authentication failed. Please verify the test credentials or login flow.");
    }

    // Cache valid session
    authSessionCache.set(session);
    return session;
  }

  /**
   * Fail-Fast Post-Authentication Verification Probe.
   * Checks if page is still stuck on login form after authentication.
   */
  public async verifySessionPostAuth(session: AuthSession, websiteUrl: string): Promise<boolean> {
    logger.info({ projectId: session.projectId, websiteUrl }, "Running Fail-Fast Post-Auth Verification probe");

    if (!session.storageStatePath) {
      // Non-browser or header session
      return true;
    }

    let browser = null;
    try {
      browser = await chromium.launch({ headless: true });
      const context = await browser.newContext({ storageState: session.storageStatePath });
      const page = await context.newPage();

      await page.goto(websiteUrl, { waitUntil: "domcontentloaded", timeout: 10000 });
      const currentUrl = page.url().toLowerCase();

      // Check if redirected or still on login page
      const isLoginPage = currentUrl.includes("/login") || currentUrl.includes("/auth") || currentUrl.includes("/signin");
      const passwordInputCount = await page.locator('input[type="password"]').count();

      if (isLoginPage || passwordInputCount > 0) {
        logger.warn({ currentUrl, passwordInputCount }, "Verification detected page is still on login screen");
        return false;
      }

      logger.info("Post-authentication verification probe passed successfully");
      return true;
    } catch (err) {
      logger.error({ err }, "Error during post-auth verification probe");
      return false;
    } finally {
      if (browser) await browser.close();
    }
  }

  /** Invalidate session for a project */
  public invalidateSession(projectId: string): void {
    authSessionCache.invalidate(projectId);
  }
}

export const authManager = AuthManager.getInstance();
