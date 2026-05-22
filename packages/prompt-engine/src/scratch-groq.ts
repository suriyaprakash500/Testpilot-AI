import "@testpilot/shared";
import { complete } from "./client.js";

async function main() {
  console.log("Testing Groq completion...");
  try {
    const result = await complete(
      [
        { role: "system", content: "You are a helpful assistant." },
        { role: "user", content: "Hello! Reply in exactly one word." },
      ],
      { skipCache: true }
    );
    console.log("Groq connection successful! Response:", result.content);
    console.log("Tokens used:", result.inputTokens + result.outputTokens);
  } catch (err) {
    console.error("Groq connection failed:", err);
  }
}

main().catch(console.error);
