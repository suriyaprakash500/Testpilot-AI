import "@testpilot/shared";
import { getDb, closeDb } from "./client.js";
import { testRuns, testCases } from "./schema.js";

import { eq } from "drizzle-orm";

async function main() {
  const db = getDb();
  const cases = await db.select().from(testCases);
  console.log("All Test Cases:");
  console.log(JSON.stringify(cases, null, 2));
  await closeDb();
}

main().catch(console.error);
