import type { ToolDefinition } from "@testpilot/types";
import { toolRegistry } from "./registry.js";

/** Tool metadata: Creates a GitHub Pull Request */
export const createPullRequestTool: ToolDefinition = {
  name: "create_pull_request",
  description: "Creates a new git branch and opens a Pull Request on GitHub containing generated/healed Playwright tests.",
  handlerKey: "handler:github:create-pr",
  parameters: {
    type: "object",
    properties: {
      repoUrl: { type: "string", description: "Target GitHub repo URL" },
      githubToken: { type: "string", description: "User's GitHub access token" },
      title: { type: "string", description: "PR title" },
      body: { type: "string", description: "PR description body" },
      files: {
        type: "array",
        items: {
          type: "object",
          properties: {
            path: { type: "string" },
            content: { type: "string" },
          },
        },
      },
    },
    required: ["repoUrl", "githubToken", "title", "body", "files"],
  },
};

toolRegistry.register(createPullRequestTool);
