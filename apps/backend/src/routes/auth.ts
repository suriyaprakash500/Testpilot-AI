import { Router, type Request, type Response, type NextFunction } from "express";
import { generateToken, requireAuth, type AuthRequest } from "../middleware/auth.js";
import { createLogger, encrypt } from "@testpilot/shared";
import { getDb, users, eq } from "@testpilot/database";

const logger = createLogger("auth-routes");
const router: Router = Router();

/**
 * GET /api/auth/github
 * Redirect to GitHub OAuth authorization page
 */
router.get("/github", (req: Request, res: Response) => {
  const clientId = process.env["GITHUB_CLIENT_ID"];
  const redirectUri = `${process.env["BACKEND_URL"] || "http://localhost:3001"}/api/auth/github/callback`;

  const url = new URL("https://github.com/login/oauth/authorize");
  url.searchParams.set("client_id", clientId || "");
  url.searchParams.set("redirect_uri", redirectUri);
  url.searchParams.set("scope", "repo user:email read:org");
  url.searchParams.set("state", crypto.randomUUID());

  res.redirect(url.toString());
});

/**
 * GET /api/auth/github/callback
 * Handle GitHub OAuth callback, exchange code for token
 */
router.get("/github/callback", async (req: Request, res: Response, next: NextFunction) => {
  try {
    const { code } = req.query;
    if (!code || typeof code !== "string") {
      res.status(400).json({ success: false, error: { code: "MISSING_CODE", message: "Missing OAuth code" } });
      return;
    }

    // Exchange code for access token
    const tokenRes = await fetch("https://github.com/login/oauth/access_token", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        client_id: process.env["GITHUB_CLIENT_ID"],
        client_secret: process.env["GITHUB_CLIENT_SECRET"],
        code,
      }),
    });

    const tokenData = (await tokenRes.json()) as { access_token?: string; error?: string };
    if (!tokenData.access_token) {
      res.status(400).json({ success: false, error: { code: "OAUTH_FAILED", message: tokenData.error || "Failed to exchange code" } });
      return;
    }

    // Get user info from GitHub
    const userRes = await fetch("https://api.github.com/user", {
      headers: { Authorization: `Bearer ${tokenData.access_token}` },
    });
    const userData = (await userRes.json()) as {
      id: number; login: string; email: string | null;
      name: string | null; avatar_url: string;
    };

    // Get email if not public
    let email = userData.email;
    if (!email) {
      const emailRes = await fetch("https://api.github.com/user/emails", {
        headers: { Authorization: `Bearer ${tokenData.access_token}` },
      });
      const emails = (await emailRes.json()) as Array<{ email: string; primary: boolean }>;
      email = emails.find((e) => e.primary)?.email || emails[0]?.email || `${userData.login}@users.noreply.github.com`;
    }

    // Upsert user in database with githubId, encrypted token, etc.
    const db = getDb();
    const displayName = userData.name || userData.login || "GitHub User";
    const [user] = await db
      .insert(users)
      .values({
        email: email!,
        name: displayName,
        githubId: String(userData.id),
        avatarUrl: userData.avatar_url,
        githubToken: encrypt(tokenData.access_token),
      })
      .onConflictDoUpdate({
        target: users.githubId,
        set: {
          email: email!,
          name: displayName,
          avatarUrl: userData.avatar_url,
          githubToken: encrypt(tokenData.access_token),
        },
      })
      .returning();

    // Generate JWT with internal user UUID
    const jwt = generateToken(user!.id, email);

    // Redirect to frontend with token
    const frontendUrl = process.env["FRONTEND_URL"] || "http://localhost:3000";
    res.redirect(`${frontendUrl}/auth/callback?token=${jwt}`);
  } catch (err) {
    next(err);
  }
});

/**
 * GET /api/auth/me
 * Get current authenticated user info
 */
router.get("/me", requireAuth, async (req: AuthRequest, res: Response, next: NextFunction) => {
  try {
    const db = getDb();
    const [user] = await db.select().from(users).where(eq(users.id, req.userId!));
    if (!user) {
      res.status(404).json({
        success: false,
        error: { code: "NOT_FOUND", message: "User not found" },
      });
      return;
    }
    res.json({
      success: true,
      data: {
        id: user.id,
        email: user.email,
        name: user.name,
        avatarUrl: user.avatarUrl,
      },
    });
  } catch (err) {
    next(err);
  }
});

export { router as authRoutes };
