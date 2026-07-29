import type { ToolDefinition } from "@testpilot/types";
import { toolRegistry } from "./registry.js";

/** Tool metadata: Scans target website URL for interactive DOM elements */
export const inspectDomNodesTool: ToolDefinition = {
  name: "inspect_dom_nodes",
  description: "Launches browser to scan web page and extract interactive DOM elements.",
  handlerKey: "handler:browser:inspect-dom",
  parameters: {
    type: "object",
    properties: {
      url: { type: "string", description: "Target webpage URL to inspect" },
    },
    required: ["url"],
  },
};

/** Tool metadata: Executes Playwright test code snippet */
export const runPlaywrightSuiteTool: ToolDefinition = {
  name: "run_playwright_suite",
  description: "Executes a Playwright test code snippet in a headless browser sandbox.",
  handlerKey: "handler:browser:run-suite",
  parameters: {
    type: "object",
    properties: {
      testCode: { type: "string", description: "Playwright TypeScript code string" },
      testName: { type: "string", description: "Name/identifier for test scenario" },
    },
    required: ["testCode", "testName"],
  },
};

toolRegistry.registerMany([inspectDomNodesTool, runPlaywrightSuiteTool]);
