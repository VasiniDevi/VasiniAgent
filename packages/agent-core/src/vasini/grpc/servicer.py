"""gRPC AgentService implementation.

MUST: Propagate correlation metadata (trace_id, tenant_id, agent_id) in every RPC.
Single code path: requires generated protobuf stubs (`make proto`).
"""

from __future__ import annotations

import uuid as uuid_mod
from dataclasses import dataclass

import grpc

from vasini.agent.v1 import agent_pb2, agent_pb2_grpc
from vasini.runtime.state import TaskState


@dataclass
class TaskRecord:
    task_id: str
    tenant_id: str
    pack_id: str
    state: str
    output: str = ""


def _extract_metadata(context, key: str) -> str:
    for k, v in context.invocation_metadata():
        if k == key:
            return v
    return ""


class AgentServicer(agent_pb2_grpc.AgentServiceServicer):

    def __init__(self) -> None:
        self._tasks: dict[str, TaskRecord] = {}

    async def _execute_agent(
        self, pack_id: str, tenant_id: str, input_text: str
    ) -> object:
        from vasini.runtime.agent import AgentResult

        return AgentResult(
            output=f"Stub response for pack={pack_id}",
            state=TaskState.DONE,
            steps_taken=1,
            messages=[],
        )

    async def RunAgent(self, request, context):
        if not request.tenant_id:
            await context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, "tenant_id is required"
            )
            return

        if not request.input:
            await context.abort(
                grpc.StatusCode.INVALID_ARGUMENT, "input is required"
            )
            return

        trace_id = _extract_metadata(context, "trace_id") or str(uuid_mod.uuid4())

        task_id = str(uuid_mod.uuid4())
        record = TaskRecord(
            task_id=task_id,
            tenant_id=request.tenant_id,
            pack_id=request.pack_id,
            state="running",
        )
        self._tasks[task_id] = record

        context.set_trailing_metadata([
            ("trace_id", trace_id),
            ("tenant_id", request.tenant_id),
            ("task_id", task_id),
        ])

        result = await self._execute_agent(
            request.pack_id, request.tenant_id, request.input
        )

        record.state = result.state.value
        record.output = result.output

        yield agent_pb2.RunAgentResponse(text_chunk=result.output)
        yield agent_pb2.RunAgentResponse(
            status=agent_pb2.AgentStatus(
                task_id=task_id,
                state=agent_pb2.TASK_STATE_DONE,
                pack_id=request.pack_id,
            )
        )

    async def GetAgentStatus(self, request, context):
        record = self._tasks.get(request.task_id)
        if record:
            state_map = {
                "queued": agent_pb2.TASK_STATE_QUEUED,
                "running": agent_pb2.TASK_STATE_RUNNING,
                "done": agent_pb2.TASK_STATE_DONE,
                "failed": agent_pb2.TASK_STATE_FAILED,
                "cancelled": agent_pb2.TASK_STATE_CANCELLED,
            }
            return agent_pb2.AgentStatus(
                task_id=record.task_id,
                state=state_map.get(record.state, agent_pb2.TASK_STATE_UNSPECIFIED),
                pack_id=record.pack_id,
            )
        return agent_pb2.AgentStatus(
            task_id=request.task_id,
            state=agent_pb2.TASK_STATE_UNSPECIFIED,
        )

    async def CancelAgent(self, request, context):
        record = self._tasks.get(request.task_id)
        if record:
            record.state = "cancelled"
        return agent_pb2.CancelAgentResponse(success=True)
