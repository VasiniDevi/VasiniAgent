import Fastify, { type FastifyInstance } from "fastify";
import { tenantMiddleware } from "./middleware/tenant.js";
import { correlationMiddleware } from "./middleware/correlation.js";
import { agentRoutes } from "./routes/agents.js";
import { AgentGrpcClient } from "./grpc/client.js";

export interface ServerConfig {
  grpcTarget: string;
  host?: string;
  port?: number;
}

export async function buildServer(config: ServerConfig): Promise<FastifyInstance> {
  const server = Fastify({
    logger: false,
  });

  const grpcClient = new AgentGrpcClient({ target: config.grpcTarget });

  server.addHook("onRequest", correlationMiddleware);

  server.get("/health", async () => ({ status: "ok" }));
  server.get("/ready", async () => ({ status: "ready" }));

  server.register(
    async (scoped) => {
      scoped.addHook("onRequest", tenantMiddleware);
      scoped.register(agentRoutes, { grpcClient, prefix: "/agents" });
    },
    { prefix: "/api/v1" }
  );

  return server;
}
