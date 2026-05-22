import type { GroqMessage } from "../client.js";
import type { TestScenario } from "@testpilot/types";

/** Build prompt for generating Playwright test code from a scenario */
export function buildTestGenerationPrompt(context: {
  scenario: TestScenario;
  websiteUrl: string;
  framework: string;
}): GroqMessage[] {
  return [
    {
      role: "system",
      content: `You are an expert Playwright test engineer. Generate production-quality Playwright test code.

You MUST respond with valid JSON:
{
  "testName": "descriptive test name",
  "testCode": "// full Playwright test code as a string",
  "locators": ["page.getByRole('link', { name: 'Home' })", "page.getByTestId('nav')"]
}

Playwright test rules:
1. Use ROBUST locators: getByRole(), getByText(), getByLabel(), getByTestId() — NEVER use fragile CSS selectors
2. Use page.waitForLoadState('networkidle') after navigation
3. Add expect() assertions for every step
4. Use test.describe() and test() blocks properly
5. Add reasonable timeouts (30s max)
6. Handle dynamic content with waitFor patterns
7. Take screenshot on assertion for debugging
8. Use 'import { test, expect } from "@playwright/test"' at the top
9. The test must be a complete, runnable file
10. Use descriptive test names

DO NOT:
- Use page.locator('div.class-name') or CSS selectors
- Skip assertions
- Use hardcoded waits (page.waitForTimeout)
- Generate incomplete code`,
    },
    {
      role: "user",
      content: `Generate a Playwright test for:

Website: ${context.websiteUrl}
Framework: ${context.framework}

Scenario: ${context.scenario.name}
Description: ${context.scenario.description}
Route: ${context.scenario.route}
Type: ${context.scenario.type}

Steps:
${context.scenario.steps.map((s, i) => `${i + 1}. ${s}`).join("\n")}

Expected Assertions:
${context.scenario.assertions.map((a) => `- ${a}`).join("\n")}`,
    },
  ];
}
