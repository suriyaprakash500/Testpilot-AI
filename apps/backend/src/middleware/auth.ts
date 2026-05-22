import type { Request, Response, NextFunction } from "express";
import jwt from "jsonwebtoken";
import { AuthError } from "@testpilot/shared";

export interface AuthRequest extends Request {
  userId?: string;
  userEmail?: string;
}

const JWT_SECRET = process.env["JWT_SECRET"] || "dev-secret-change-in-production";

/** Verify JWT from Authorization header */
export function requireAuth(req: AuthRequest, _res: Response, next: NextFunction) {
  const authHeader = req.headers.authorization;
  if (!authHeader?.startsWith("Bearer ")) {
    return next(new AuthError("Missing authorization header"));
  }

  const token = authHeader.slice(7);
  try {
    const payload = jwt.verify(token, JWT_SECRET) as { userId: string; email: string };
    req.userId = payload.userId;
    req.userEmail = payload.email;
    next();
  } catch {
    next(new AuthError("Invalid or expired token"));
  }
}

/** Generate a JWT token for a user */
export function generateToken(userId: string, email: string): string {
  return jwt.sign({ userId, email }, JWT_SECRET, { expiresIn: "7d" });
}
