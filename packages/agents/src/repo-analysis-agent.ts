import { BaseAgent } from "./base-agent.js";
import { type AgentContext, type AgentType, type RepoAnalysis, repoAnalysisOutputSchema } from "@testpilot/types";
import { complete, parseJsonResponse, buildRepoAnalysisPrompt } from "@testpilot/prompt-engine";
import { cloneRepo, getFileTree, readFile } from "@testpilot/github-engine";

const CONFIG_FILES = [
  "next.config.js", "next.config.ts", "next.config.mjs",
  "vite.config.ts", "vite.config.js",
  "nuxt.config.ts", "angular.json", "svelte.config.js",
  "astro.config.mjs", "remix.config.js",
  "tsconfig.json", ".env.example",
];

export class RepoAnalysisAgent extends BaseAgent {
  readonly type: AgentType = "repo-analysis";

  protected async execute(context: AgentContext): Promise<RepoAnalysis> {
    const { projectId, runId } = context;

    // Step 1: Clone the repository
    this.progress("Cloning repository...", 10);
    const repoPath = await cloneRepo(projectId);

    // Step 2: Get file tree (depth-limited)
    this.progress("Scanning file tree...", 30);
    const fileTree = await getFileTree(repoPath, { maxDepth: 4, maxFiles: 200 });

    // Step 3: Read package.json
    this.progress("Reading configuration...", 50);
    const packageJson = await readFile(repoPath, "package.json").catch(() => "{}");

    // Step 4: Read config files
    const configContents: string[] = [];
    for (const configFile of CONFIG_FILES) {
      const content = await readFile(repoPath, configFile).catch(() => null);
      if (content) {
        configContents.push(`--- ${configFile} ---\n${content}`);
      }
    }

    // Step 5: Send to AI for analysis
    this.progress("Analyzing with AI...", 70);
    const messages = buildRepoAnalysisPrompt({
      fileTree,
      packageJson,
      configFiles: configContents,
    });

    const result = await complete(messages, { jsonMode: true });
    this.addTokens(result.inputTokens, result.outputTokens);

    // Step 6: Parse and validate
    this.progress("Validating analysis...", 90);
    const raw = parseJsonResponse(result.content);
    const parsed = repoAnalysisOutputSchema.parse(raw);

    const analysis: RepoAnalysis = {
      id: crypto.randomUUID(),
      projectId,
      ...parsed,
      analyzedAt: new Date(),
    };

    this.progress("Analysis complete", 100);
    return analysis;
  }
}
