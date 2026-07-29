import type { CredentialRef } from "@testpilot/types";
import { createLogger } from "@testpilot/shared";
import { getDb, projects, eq } from "@testpilot/database";

const logger = createLogger("credential-store");

export interface DecryptedCredential {
  username?: string;
  password?: string;
  secretToken?: string;
}

/**
 * CredentialStore Abstraction.
 * Decouples raw secret/password retrieval from database storage.
 * Easily pluggable into AWS Secrets Manager, HashiCorp Vault, or Azure Key Vault.
 */
export class CredentialStore {
  private static instance: CredentialStore;

  private constructor() {}

  public static getInstance(): CredentialStore {
    if (!CredentialStore.instance) {
      CredentialStore.instance = new CredentialStore();
    }
    return CredentialStore.instance;
  }

  /** Retrieve and decrypt credential secrets for a given project */
  public async getCredential(projectId: string): Promise<DecryptedCredential | null> {
    logger.info({ projectId }, "Retrieving project credentials from CredentialStore");

    try {
      const db = getDb();
      const [project] = await db.select().from(projects).where(eq(projects.id, projectId));

      if (!project || (!project.testEmail && !project.testPassword)) {
        return null;
      }

      return {
        username: project.testEmail || undefined,
        password: project.testPassword || undefined,
      };
    } catch (err) {
      logger.error({ projectId, err }, "Failed to fetch credentials from store");
      return null;
    }
  }
}

export const credentialStore = CredentialStore.getInstance();
