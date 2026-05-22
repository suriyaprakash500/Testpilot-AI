import type { GroqMessage } from "../client.js";

/** Build prompt for analyzing a test failure */
export function buildFailureAnalysisPrompt(context: {
  testName: string;
  testCode: string;
  errorMessage: string;
  stackTrace: string | null;
  consoleLogs: string[];
  screenshotDescription?: string;
}): GroqMessage[] {
  return [
    {
      role: "system",
      content: `You are an expert test failure analyst. Analyze the failing Playwright test and provide a root cause analysis.

You MUST respond with valid JSON:
{
  "type": "assertion" | "timeout" | "selector" | "network" | "script" | "unknown",
  "rootCause": "Clear explanation of why the test failed",
  "suggestedFix": "Specific code or configuration change to fix the issue",
  "confidence": 0.85,
  "details": {
    "affectedElement": "element description if relevant",
    "expectedBehavior": "what should have happened",
    "actualBehavior": "what actually happened"
  }
}

Analysis rules:
- "assertion": expect() failed — wrong value, missing element
- "timeout": page/element didn't load in time
- "selector": element not found, locator changed
- "network": API call failed, resource not loaded
- "script": JavaScript error on the page
- "unknown": can't determine
- Be specific in rootCause — don't just repeat the error
- suggestedFix should be actionable code or steps
- confidence: 0-1, how sure you are of the root cause`,
    },
    {
      role: "user",
      content: `Analyze this test failure:

TEST: ${context.testName}

CODE:
\`\`\`typescript
${context.testCode}
\`\`\`

ERROR: ${context.errorMessage}

${context.stackTrace ? `STACK TRACE:\n${context.stackTrace}` : ""}

${context.consoleLogs.length > 0 ? `CONSOLE LOGS:\n${context.consoleLogs.join("\n")}` : ""}

${context.screenshotDescription ? `SCREENSHOT DESCRIPTION: ${context.screenshotDescription}` : ""}`,
    },
  ];
}
