import type { WebSocketServer, WebSocket } from "ws";
import { createLogger } from "@testpilot/shared";

const logger = createLogger("websocket");

interface WSClient {
  ws: WebSocket;
  subscriptions: Set<string>; // projectId or runId
}

const clients = new Map<string, WSClient>();

export function setupWebSocket(wss: WebSocketServer) {
  wss.on("connection", (ws, req) => {
    const clientId = crypto.randomUUID();
    clients.set(clientId, { ws, subscriptions: new Set() });

    logger.info({ clientId }, "WebSocket client connected");

    ws.on("message", (raw) => {
      try {
        const msg = JSON.parse(raw.toString()) as {
          type: "subscribe" | "unsubscribe";
          channel: string;
        };

        const client = clients.get(clientId);
        if (!client) return;

        if (msg.type === "subscribe") {
          client.subscriptions.add(msg.channel);
        } else if (msg.type === "unsubscribe") {
          client.subscriptions.delete(msg.channel);
        }
      } catch {
        // ignore malformed messages
      }
    });

    ws.on("close", () => {
      clients.delete(clientId);
      logger.info({ clientId }, "WebSocket client disconnected");
    });

    // Send initial ping
    ws.send(JSON.stringify({ type: "connected", clientId }));
  });
}

/** Broadcast an event to all clients subscribed to a channel */
export function broadcast(channel: string, event: Record<string, unknown>) {
  const payload = JSON.stringify({ channel, ...event });
  for (const [, client] of clients) {
    if (client.subscriptions.has(channel) && client.ws.readyState === 1) {
      client.ws.send(payload);
    }
  }
}
