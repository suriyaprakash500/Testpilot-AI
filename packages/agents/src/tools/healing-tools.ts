import type { ToolDefinition } from "@testpilot/types";
import { toolRegistry } from "./registry.js";

/** Tool metadata: Analyzes stack trace and repairs locators */
export const repairLocatorTool: ToolDefinition = {
  name: "repair_locator",
  description: "Analyzes broken test locators and stack traces to generate auto-healed resilient CSS/role selectors.",
  handlerKey: "handler:healing:repair-locator",
  parameters: {
    type: "object",
    properties: {
      failedSelector: { type: "string", description: "The locator selector that failed" },
      errorMessage: { type: "string", description: "Error message or stack trace from Playwright" },
      domSnapshot: { type: "string", description: "DOM snapshot html surrounding the failure" },
    },
    required: ["failedSelector", "errorMessage"],
  },
};

toolRegistry.register(repairLocatorTool);
