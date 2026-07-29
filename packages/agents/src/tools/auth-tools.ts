import type { ToolDefinition } from "@testpilot/types";
import { toolRegistry } from "./registry.js";

/** Tool metadata: Authenticates session and retrieves active AuthSession reference */
export const authenticateSessionTool: ToolDefinition = {
  name: "authenticate_session",
  description: "Authenticates project session using configured credentials or cached AuthSession.",
  handlerKey: "handler:auth:session",
  parameters: {
    type: "object",
    properties: {
      projectId: { type: "string", description: "Target project ID" },
      websiteUrl: { type: "string", description: "Target website URL" },
    },
    required: ["projectId", "websiteUrl"],
  },
};

toolRegistry.register(authenticateSessionTool);
