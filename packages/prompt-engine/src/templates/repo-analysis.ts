import type { GroqMessage } from "../client.js";

/** Build prompt for analyzing a GitHub repository structure */
export function buildRepoAnalysisPrompt(context: {
  fileTree: string;
  packageJson: string;
  configFiles: string[];
}): GroqMessage[] {
  return [
    {
      role: "system",
      content: `You are an expert web application analyzer. Given a repository's file structure and configuration, analyze the application and output a structured JSON report.

You MUST respond with valid JSON only, no explanations. Follow this exact schema:
{
  "framework": "nextjs" | "react" | "vue" | "nuxt" | "angular" | "svelte" | "astro" | "remix" | "express" | "unknown",
  "language": "typescript" | "javascript",
  "routes": [{ "path": "/route", "component": "ComponentName" | null, "isDynamic": false, "methods": ["GET"] }],
  "components": [{ "name": "ComponentName", "filePath": "src/components/Foo.tsx", "type": "page" | "layout" | "component" | "api" }],
  "hasAuth": true | false,
  "hasApi": true | false,
  "entryPoints": ["src/app/page.tsx"],
  "dependencies": { "react": "^18.0.0" }
}

Rules:
- Detect framework from config files and dependencies
- Extract routes from file-based routing (pages/, app/) or router configs
- Mark dynamic routes (e.g., [id], :id) with isDynamic: true
- Detect auth by looking for auth libraries, login pages, middleware
- List only key UI components, not every file
- Keep the output concise — max 30 routes, max 50 components`,
    },
    {
      role: "user",
      content: `Analyze this repository:

FILE TREE:
${context.fileTree}

PACKAGE.JSON:
${context.packageJson}

CONFIG FILES:
${context.configFiles.join("\n\n")}`,
    },
  ];
}
