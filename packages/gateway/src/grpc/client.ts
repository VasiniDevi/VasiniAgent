import { v4 as uuidv4 } from "uuid";

export interface GrpcClientConfig {
  target: string;
}

export interface GrpcCallMetadata {
  traceId: string;
  tenantId: string;
}

export class AgentGrpcClient {
  private target: string;

  constructor(config: GrpcClientConfig) {
    this.target = config.target;
  }

  async runAgent(params: {
    packId: string;
    tenantId: string;
    input: string;
    sessionId?: string;
    idempotencyKey?: string;
    metadata?: Record<string, string>;
    traceId?: string;
  }): Promise<{ taskId: string }> {
    return { taskId: uuidv4() };
  }

  async getStatus(params: {
    taskId: string;
    tenantId: string;
    traceId?: string;
  }): Promise<{
    taskId: string;
    state: string;
    packId: string;
    packVersion: string;
  }> {
    return {
      taskId: params.taskId,
      state: "queued",
      packId: "unknown",
      packVersion: "0.0.0",
    };
  }
}
