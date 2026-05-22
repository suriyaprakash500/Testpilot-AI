import { chromium, type Browser, type BrowserContext } from "playwright";
import { createLogger } from "@testpilot/shared";

const logger = createLogger("browser-manager");

let _browser: Browser | null = null;

/** Get or launch a shared browser instance */
export async function getBrowser(): Promise<Browser> {
  if (_browser?.isConnected()) return _browser;

  logger.info("Launching browser");
  _browser = await chromium.launch({
    headless: true,
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-dev-shm-usage",
      "--disable-gpu",
    ],
  });

  _browser.on("disconnected", () => {
    logger.warn("Browser disconnected");
    _browser = null;
  });

  return _browser;
}

/** Create an isolated browser context for a test run */
export async function createContext(options?: {
  viewport?: { width: number; height: number };
  userAgent?: string;
  baseURL?: string;
}): Promise<BrowserContext> {
  const browser = await getBrowser();
  const context = await browser.newContext({
    viewport: options?.viewport || { width: 1280, height: 720 },
    userAgent: options?.userAgent,
    baseURL: options?.baseURL,
    ignoreHTTPSErrors: true,
    recordVideo: undefined, // enable per-run if needed
  });

  // Set default timeouts
  context.setDefaultTimeout(5_000);
  context.setDefaultNavigationTimeout(5_000);

  return context;
}

/** Close the shared browser instance */
export async function closeBrowser() {
  if (_browser) {
    await _browser.close();
    _browser = null;
    logger.info("Browser closed");
  }
}
