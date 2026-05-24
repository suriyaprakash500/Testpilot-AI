import express from "express";
import cors from "cors";
import helmet from "helmet";
import compression from "compression";
import http from "node:http";
import path from "node:path";
import { WebSocketServer } from "ws";
import { createLogger } from "@testpilot/shared";
import { getDb, closeDb } from "@testpilot/database";
import { closeQueues } from "@testpilot/queue";
import { closeBrowser } from "@testpilot/playwright-engine";
import { projectRoutes } from "./routes/projects.js";
import { testRunRoutes } from "./routes/test-runs.js";
import { authRoutes } from "./routes/auth.js";
import { webhookRoutes } from "./routes/webhooks.js";
import { errorHandler } from "./middleware/error-handler.js";
import { setupWebSocket } from "./ws/handler.js";

const logger = createLogger("server");

const app = express();
const PORT = parseInt(process.env["BACKEND_PORT"] || "3001", 10);

// --- Middleware ---
app.use(helmet({ contentSecurityPolicy: false }));
app.use(cors({
  origin: process.env["FRONTEND_URL"] || "http://localhost:3000",
  credentials: true,
}));
app.use(compression());
app.use(express.json({
  limit: "10mb",
  verify: (req: any, _res, buf) => {
    req.rawBody = buf;
  }
}));

// --- Health check ---
app.get("/api/health", (_req, res) => {
  res.json({ status: "ok", timestamp: new Date().toISOString() });
});

// --- Serve E2E Test Artifacts/Screenshots ---
app.get("/api/artifacts/*", (req, res) => {
  const reqUrlPath = req.path;
  const prefix = "/api/artifacts/";
  if (!reqUrlPath.startsWith(prefix)) {
    return res.status(400).send("Invalid path");
  }
  const relativePath = decodeURIComponent(reqUrlPath.slice(prefix.length));
  const cleanPath = relativePath.replace(/^artifacts[\/\\]/, "");
  const artifactsDir = path.resolve(process.env["ARTIFACTS_DIR"] || "./artifacts");
  const filePath = path.join(artifactsDir, cleanPath);

  if (!filePath.startsWith(artifactsDir)) {
    return res.status(403).send("Forbidden");
  }

  res.sendFile(filePath);
});

// --- Routes ---
app.use("/api/auth", authRoutes);
app.use("/api/projects", projectRoutes);
app.use("/api/test-runs", testRunRoutes);
app.use("/api/webhooks", webhookRoutes);

// --- Error handler ---
app.use(errorHandler);

// --- HTTP + WebSocket server ---
const server = http.createServer(app);
const wss = new WebSocketServer({ server, path: "/ws" });
setupWebSocket(wss);

// --- Start ---
server.listen(PORT, () => {
  logger.info({ port: PORT }, "TestPilot API server started");
});

// --- Graceful shutdown ---
async function shutdown(signal: string) {
  logger.info({ signal }, "Shutting down...");
  server.close();
  await closeQueues();
  await closeBrowser();
  await closeDb();
  process.exit(0);
}

process.on("SIGTERM", () => shutdown("SIGTERM"));
process.on("SIGINT", () => shutdown("SIGINT"));
