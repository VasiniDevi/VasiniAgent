import type { FastifyRequest, FastifyReply } from "fastify";
import { v4 as uuidv4 } from "uuid";

export async function correlationMiddleware(
  request: FastifyRequest,
  reply: FastifyReply
): Promise<void> {
  const requestId =
    (request.headers["x-request-id"] as string) || uuidv4();

  (request as any).requestId = requestId;
  reply.header("x-request-id", requestId);
}
