import type { TestCase, FailureReport, TestRunSummary } from "@testpilot/types";

export interface ReportData {
  runId: string;
  projectName: string;
  summary: TestRunSummary;
  testCases: TestCase[];
  failures: FailureReport[];
  generatedAt: Date;
}

/** Generate a JSON report for a test run */
export function generateJsonReport(data: ReportData): Record<string, unknown> {
  return {
    meta: {
      runId: data.runId,
      project: data.projectName,
      generatedAt: data.generatedAt.toISOString(),
    },
    summary: data.summary,
    tests: data.testCases.map((tc) => ({
      name: tc.name,
      status: tc.status,
      durationMs: tc.durationMs,
      error: tc.errorMessage,
    })),
    failures: data.failures.map((f) => ({
      testCaseId: f.testCaseId,
      type: f.type,
      rootCause: f.rootCause,
      suggestedFix: f.suggestedFix,
    })),
  };
}

/** Generate an HTML report string */
export function generateHtmlReport(data: ReportData): string {
  const passRate = data.summary.total > 0
    ? Math.round((data.summary.passed / data.summary.total) * 100)
    : 0;

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>TestPilot Report — ${data.projectName}</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0a; color: #e5e5e5; padding: 2rem; }
    .header { margin-bottom: 2rem; }
    .header h1 { font-size: 1.5rem; color: #fff; margin-bottom: 0.5rem; }
    .header p { color: #888; font-size: 0.875rem; }
    .summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 2rem; }
    .stat { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 1.25rem; }
    .stat-value { font-size: 2rem; font-weight: 700; }
    .stat-label { color: #888; font-size: 0.75rem; text-transform: uppercase; margin-top: 0.25rem; }
    .passed { color: #22c55e; }
    .failed { color: #ef4444; }
    .tests { margin-top: 1.5rem; }
    .test { background: #1a1a1a; border: 1px solid #333; border-radius: 8px; padding: 1rem; margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.75rem; }
    .test-icon { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
    .test-icon.pass { background: #22c55e; }
    .test-icon.fail { background: #ef4444; }
    .test-name { flex: 1; }
    .test-duration { color: #666; font-size: 0.75rem; }
    .failure-detail { margin-top: 0.5rem; padding: 0.75rem; background: #0f0f0f; border-radius: 4px; font-size: 0.8rem; color: #f87171; }
  </style>
</head>
<body>
  <div class="header">
    <h1>🧪 TestPilot AI Report</h1>
    <p>${data.projectName} — ${data.generatedAt.toISOString()}</p>
  </div>
  <div class="summary">
    <div class="stat"><div class="stat-value">${data.summary.total}</div><div class="stat-label">Total Tests</div></div>
    <div class="stat"><div class="stat-value passed">${data.summary.passed}</div><div class="stat-label">Passed</div></div>
    <div class="stat"><div class="stat-value failed">${data.summary.failed}</div><div class="stat-label">Failed</div></div>
    <div class="stat"><div class="stat-value">${passRate}%</div><div class="stat-label">Pass Rate</div></div>
  </div>
  <div class="tests">
    <h2 style="margin-bottom: 1rem; font-size: 1.125rem;">Test Results</h2>
    ${data.testCases
      .map((tc) => {
        const failure = data.failures.find((f) => f.testCaseId === tc.id);
        return `<div class="test">
          <div class="test-icon ${tc.status === "passed" ? "pass" : "fail"}"></div>
          <div class="test-name">${escapeHtml(tc.name)}</div>
          <div class="test-duration">${tc.durationMs ? `${tc.durationMs}ms` : "—"}</div>
        </div>
        ${failure ? `<div class="failure-detail"><strong>Root Cause:</strong> ${escapeHtml(failure.rootCause || "Unknown")}<br><strong>Fix:</strong> ${escapeHtml(failure.suggestedFix || "N/A")}</div>` : ""}`;
      })
      .join("\n")}
  </div>
</body>
</html>`;
}

function escapeHtml(str: string): string {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
