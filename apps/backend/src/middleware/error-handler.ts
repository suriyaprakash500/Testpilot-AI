import type { Request, Response, NextFunction } from "express";
import { AppError } from "@testpilot/shared";
import { createLogger } from "@testpilot/shared";
import { ZodError } from "zod";

const logger = createLogger("error-handler");

export function errorHandler(err: Error, req: Request, res: Response, _next: NextFunction) {
  if (err instanceof AppError) {
    res.status(err.statusCode).json({
      success: false,
      error: err.toJSON(),
    });
    return;
  }

  if (err instanceof ZodError) {
    res.status(400).json({
      success: false,
      error: {
        code: "VALIDATION_ERROR",
        message: "Invalid request data",
        details: err.errors,
      },
    });
    return;
  }

  logger.error({ err, path: req.path }, "Unhandled error");

  res.status(500).json({
    success: false,
    error: {
      code: "INTERNAL_ERROR",
      message: process.env["NODE_ENV"] === "production" ? "Internal server error" : err.message,
    },
  });
}
