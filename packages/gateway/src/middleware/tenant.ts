import type { FastifyRequest, FastifyReply } from "fastify";
import { makeError } from "../errors.js";

export async function tenantMiddleware(
  request: FastifyRequest,
  reply: FastifyReply
): Promise<void> {
  const tenantId = request.headers["x-tenant-id"] as string | undefined;
  const traceId = (request as any).requestId || "unknown";

  if (!tenantId) {
    reply.status(400).send(
      makeError("MISSING_TENANT", "X-Tenant-ID header is required", traceId)
    );
    return;
  }

  (request as any).tenantId = tenantId;
}
