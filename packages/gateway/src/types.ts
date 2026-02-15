export interface RunAgentRequest {
  input: string;
  session_id?: string;
  metadata?: Record<string, string>;
}

export interface RunAgentResponse {
  task_id: string;
  status: string;
  pack_id: string;
}

export interface AgentStatusResponse {
  task_id: string;
  state: string;
  pack_id: string;
  pack_version: string;
}
