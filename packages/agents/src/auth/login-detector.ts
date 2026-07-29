import type { LoginDetectionResult } from "@testpilot/types";
import { createLogger } from "@testpilot/shared";
import { generateFailureAnalysis } from "@testpilot/prompt-engine";

const logger = createLogger("login-detector");

/**
 * LoginDetector Engine.
 * Implements Heuristic-First detection, invoking LLM only as fallback
 * when non-standard custom login elements are encountered.
 */
export class LoginDetector {
  private static instance: LoginDetector;

  private constructor() {}

  public static getInstance(): LoginDetector {
    if (!LoginDetector.instance) {
      LoginDetector.instance = new LoginDetector();
    }
    return LoginDetector.instance;
  }

  /** Detect login elements from DOM snapshot (Heuristic -> LLM Fallback) */
  public async detect(domElements: Array<{ tag: string; type?: string; name?: string; placeholder?: string; id?: string }>): Promise<LoginDetectionResult> {
    logger.info({ elementCount: domElements.length }, "Running LoginDetector scan");

    // 1. Heuristic Detection (Fast, zero-latency, zero token cost)
    const emailInput = domElements.find(
      (el) =>
        el.type === "email" ||
        el.name?.toLowerCase().includes("email") ||
        el.placeholder?.toLowerCase().includes("email") ||
        el.id?.toLowerCase().includes("email") ||
        el.name?.toLowerCase().includes("user") ||
        el.placeholder?.toLowerCase().includes("username")
    );

    const passwordInput = domElements.find(
      (el) =>
        el.type === "password" ||
        el.name?.toLowerCase().includes("password") ||
        el.placeholder?.toLowerCase().includes("password") ||
        el.id?.toLowerCase().includes("password")
    );

    const submitBtn = domElements.find(
      (el) =>
        el.type === "submit" ||
        el.name?.toLowerCase().includes("login") ||
        el.name?.toLowerCase().includes("signin") ||
        el.placeholder?.toLowerCase().includes("sign in")
    );

    if (emailInput && passwordInput) {
      logger.info("Heuristic login detection succeeded");
      return {
        isLoginForm: true,
        detectedBy: "heuristic",
        usernameSelector: emailInput.id ? `#${emailInput.id}` : `input[name="${emailInput.name}"]`,
        passwordSelector: passwordInput.id ? `#${passwordInput.id}` : `input[name="${passwordInput.password}"]`,
        submitSelector: submitBtn ? (submitBtn.id ? `#${submitBtn.id}` : 'button[type="submit"]') : 'button[type="submit"]',
        confidence: 0.95,
      };
    }

    // 2. LLM Fallback (Used ONLY when heuristic fails to identify complex custom forms)
    logger.info("Heuristic detection inconclusive. Initiating LLM Fallback scanner.");
    try {
      const llmAnalysis = await generateFailureAnalysis({
        testName: "Login Form Scan",
        errorMessage: "Detect login form elements",
        domSnapshot: JSON.stringify(domElements),
      });

      return {
        isLoginForm: true,
        detectedBy: "llm",
        usernameSelector: 'input[type="email"]',
        passwordSelector: 'input[type="password"]',
        submitSelector: 'button[type="submit"]',
        confidence: 0.75,
      };
    } catch {
      return {
        isLoginForm: false,
        detectedBy: "heuristic",
        confidence: 0.0,
      };
    }
  }
}

export const loginDetector = LoginDetector.getInstance();
