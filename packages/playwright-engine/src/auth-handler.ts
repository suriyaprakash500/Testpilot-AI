import { createContext } from "./browser-manager.js";
import { createLogger } from "@testpilot/shared";
import fs from "node:fs/promises";
import path from "node:path";

const logger = createLogger("auth-handler");

const ARTIFACTS_DIR = process.env["ARTIFACTS_DIR"] || "./artifacts";

/**
 * Authenticate against a website using heuristic form detection,
 * then save the browser storage state for reuse by test contexts.
 */
export async function authenticateAndSave(options: {
  websiteUrl: string;
  email: string;
  password: string;
  projectId: string;
  runId: string;
}): Promise<string | null> {
  const { websiteUrl, email, password, projectId, runId } = options;
  const savePath = path.join(ARTIFACTS_DIR, projectId, runId, "auth-state.json");
  await fs.mkdir(path.dirname(savePath), { recursive: true });

  const context = await createContext({ baseURL: websiteUrl });
  const page = await context.newPage();

  try {
    logger.info({ websiteUrl }, "Attempting auto-login");

    // Navigate to the site — it may redirect to a login page
    await page.goto(websiteUrl, { waitUntil: "networkidle", timeout: 15_000 });

    // Heuristic: find email/password inputs
    const emailInput = page.locator('input[type="email"], input[name="email"], input[name="username"], input[id="email"]').first();
    const passwordInput = page.locator('input[type="password"]').first();

    const hasEmailField = await emailInput.isVisible({ timeout: 3_000 }).catch(() => false);
    const hasPasswordField = await passwordInput.isVisible({ timeout: 1_000 }).catch(() => false);

    if (!hasEmailField || !hasPasswordField) {
      logger.warn("No login form detected on landing page, skipping auto-login");
      await page.close();
      await context.close();
      return null;
    }

    // Fill and submit
    await emailInput.fill(email);
    await passwordInput.fill(password);

    // Find submit button: button[type=submit], or button containing "login"/"sign in"
    const submitBtn = page.locator(
      'button[type="submit"], input[type="submit"], button:has-text("Log in"), button:has-text("Login"), button:has-text("Sign in")'
    ).first();

    const hasSubmit = await submitBtn.isVisible({ timeout: 1_000 }).catch(() => false);
    if (hasSubmit) {
      await submitBtn.click();
    } else {
      // Fallback: press Enter on password field
      await passwordInput.press("Enter");
    }

    // Wait for navigation after login
    await page.waitForLoadState("networkidle", { timeout: 10_000 }).catch(() => {});

    // Verify we left the login page (URL changed or login form is gone)
    const stillHasPassword = await page.locator('input[type="password"]').isVisible({ timeout: 1_000 }).catch(() => false);
    if (stillHasPassword) {
      logger.warn("Login may have failed — password field still visible after submission");
      await page.close();
      await context.close();
      return null;
    }

    // Save storage state
    await context.storageState({ path: savePath });
    logger.info({ savePath }, "Auth state saved successfully");

    await page.close();
    await context.close();
    return savePath;
  } catch (err) {
    logger.error({ err }, "Auto-login failed");
    await page.close().catch(() => {});
    await context.close().catch(() => {});
    return null;
  }
}
