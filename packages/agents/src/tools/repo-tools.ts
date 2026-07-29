import type { ToolDefinition } from "@testpilot/types";
import { toolRegistry } from "./registry.js";

/** Tool metadata: Scans repository tree and extracts routes and framework metadata */
export const analyzeRepoStructureTool: ToolDefinition = {
  name: "analyze_repo_structure",
  description: "Clones and analyzes repository structure, identifying framework, routes, and components.",
  handlerKey: "handler:repo:analyze",
  parameters: {
    type: "object",
    properties: {
      repoUrl: { type: "string", description: "Target GitHub repository URL" },
    },
    required: ["repoUrl"],
  },
};

/** Tool metadata: Reads content of a specific source code file */
export const readSourceFileTool: ToolDefinition = {
  name: "read_source_file",
  description: "Reads the content of a specific source code file from the cloned repository.",
  handlerKey: "handler:fs:read-source",
  parameters: {
    type: "object",
    properties: {
      relativePath: { type: "string", description: "Relative file path from repository root" },
    },
    required: ["relativePath"],
  },
};

// Register tool metadata
toolRegistry.registerMany([analyzeRepoStructureTool, readSourceFileTool]);
