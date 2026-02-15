import type { FastifyInstance } from "fastify";
import type { AgentGrpcClient } from "../grpc/client.js";
import type { RunAgentRequest } from "../types.js";
import { makeError } from "../errors.js";

export async function agentRoutes(
  fastify: FastifyInstance,
  opts: { grpcClient: AgentGrpcClient }
): Promise<void> {
  const { grpcClient } = opts;

  fastify.post<{
    Params: { packId: string };
    Body: RunAgentRequest;
  }>("/:packId/run", async (request, reply) => {
    const { packId } = request.params;
    const { input, session_id, metadata } = request.body || {};
    const tenantId = (request as any).tenantId as string;
    const traceId = (request as any).requestId as string;

    if (!input) {
      return reply.status(400).send(
        makeError("MISSING_INPUT", "input is required in request body", traceId, tenantId)
      );
    }

    const idempotencyKey = request.headers["x-idempotency-key"] as string | undefined;
    if (!idempotencyKey) {
      return reply.status(400).send(
        makeError("MISSING_IDEMPOTENCY_KEY", "X-Idempotency-Key header is required for run", traceId, tenantId)
      );
    }

    const result = await grpcClient.runAgent({
      packId,
      tenantId,
      input,
      sessionId: session_id,
      idempotencyKey,
      metadata,
      traceId,
    });

    return reply.status(202).send({
      task_id: result.taskId,
      status: "queued",
      pack_id: packId,
    });
  });

  fastify.get<{
    Params: { taskId: string };
  }>("/status/:taskId", async (request, reply) => {
    const tenantId = (request as any).tenantId as string;
    const traceId = (request as any).requestId as string;
    const { taskId } = request.params;

    const status = await grpcClient.getStatus({ taskId, tenantId, traceId });
    return reply.send(status);
  });
}
