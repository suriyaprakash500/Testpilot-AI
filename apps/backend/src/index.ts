import express from "express";
import cors from "cors";
import helmet from "helmet";
import compression from "compression";
import http from "node:http";
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
