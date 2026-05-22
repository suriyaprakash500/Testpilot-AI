import { BaseAgent } from "./base-agent.js";
import type { AgentContext, AgentType } from "@testpilot/types";
import { createIssue, createPRComment } from "@testpilot/github-engine";

export class GitHubIntegrationAgent extends BaseAgent {
  readonly type: AgentType = "github-integration";

  protected async execute(context: AgentContext): Promise<{ issuesCreated: number; commentsPosted: number }> {
    const failureReports = context.failureReports || [];
    let issuesCreated = 0;
    let commentsPosted = 0;

    if (failureReports.length === 0) {
      this.progress("No failures to report", 100);
      return { issuesCreated, commentsPosted };
    }

    this.progress("Creating GitHub issues for failures...", 30);

    // Create a summary issue for the test run
    const failedTests = (context.testCases || []).filter((t) => t.status === "failed");
    const passedCount = (context.testCases || []).filter((t) => t.status === "passed").length;

    const issueBody = [
      `## 🤖 TestPilot AI — Test Run Report`,
      "",
      `**Run ID:** \`${context.runId}\``,
      `**Results:** ✅ ${passedCount} passed | ❌ ${failedTests.length} failed`,
      "",
      "### Failures",
      "",
      ...failureReports.map((report) => {
        const testCase = failedTests.find((t) => t.id === report.testCaseId);
        return [
          `#### ❌ ${testCase?.name || "Unknown test"}`,
          `- **Type:** ${report.type}`,
          `- **Root Cause:** ${report.rootCause || "Unknown"}`,
          `- **Suggested Fix:** ${report.suggestedFix || "N/A"}`,
          "",
        ].join("\n");
      }),
    ].join("\n");

    try {
      await createIssue(context.projectId, {
        title: `[TestPilot] ${failedTests.length} test failure(s) detected`,
        body: issueBody,
        labels: ["testpilot", "bug", "automated"],
      });
      issuesCreated++;
    } catch (err) {
      this.logger.warn({ err }, "Failed to create GitHub issue");
    }

    this.progress("GitHub sync complete", 100);
    return { issuesCreated, commentsPosted };
  }
}
