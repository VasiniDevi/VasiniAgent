"""Tests for gRPC Agent Service implementation.

Requires: `make proto` to generate protobuf stubs before running.
"""

import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from vasini.grpc.servicer import AgentServicer
from vasini.runtime.state import TaskState
from vasini.agent.v1 import agent_pb2


class MockContext:
    """Mock gRPC context for testing."""
    def __init__(self, metadata: dict | None = None):
        self._metadata = metadata or {}
        self._code = None
        self._details = None
        self._aborted = False
        self._trailing_metadata = []

    def invocation_metadata(self):
        return [(k, v) for k, v in self._metadata.items()]

    def set_code(self, code):
        self._code = code

    def set_details(self, details):
        self._details = details

    def set_trailing_metadata(self, metadata):
        self._trailing_metadata = metadata

    async def abort(self, code, details):
        self._code = code
        self._details = details
        self._aborted = True
        raise Exception(f"Aborted: {details}")


class TestAgentServicer:
    def test_create_servicer(self):
        servicer = AgentServicer()
        assert servicer is not None

    @pytest.mark.asyncio
    async def test_run_agent_missing_tenant(self):
        servicer = AgentServicer()
        request = MagicMock()
        request.pack_id = "senior-python-dev"
        request.tenant_id = ""
        request.input = "Hello"
        request.idempotency_key = str(uuid.uuid4())

        context = MockContext()

        with pytest.raises(Exception, match="tenant_id is required"):
            async for _ in servicer.RunAgent(request, context):
                pass

    @pytest.mark.asyncio
    async def test_run_agent_missing_input(self):
        servicer = AgentServicer()
        request = MagicMock()
        request.pack_id = "senior-python-dev"
        request.tenant_id = "tenant-123"
        request.input = ""
        request.idempotency_key = str(uuid.uuid4())

        context = MockContext()

        with pytest.raises(Exception, match="input is required"):
            async for _ in servicer.RunAgent(request, context):
                pass

    @pytest.mark.asyncio
    async def test_run_agent_streams_response(self):
        servicer = AgentServicer()

        mock_result = MagicMock()
        mock_result.output = "Hello, I am a Python developer."
        mock_result.state = TaskState.DONE

        with patch.object(servicer, '_execute_agent', new_callable=AsyncMock, return_value=mock_result):
            request = MagicMock()
            request.pack_id = "senior-python-dev"
            request.tenant_id = "tenant-123"
            request.input = "Introduce yourself"
            request.session_id = ""
            request.idempotency_key = str(uuid.uuid4())
            request.metadata = {}

            context = MockContext(metadata={"trace_id": "trace-abc"})
            responses = []

            async for response in servicer.RunAgent(request, context):
                responses.append(response)

            assert len(responses) >= 2
            assert responses[0].HasField("text_chunk")
            assert responses[-1].HasField("status")
            assert responses[-1].status.state == agent_pb2.TASK_STATE_DONE

    @pytest.mark.asyncio
    async def test_correlation_metadata_propagated(self):
        servicer = AgentServicer()

        mock_result = MagicMock()
        mock_result.output = "Done"
        mock_result.state = TaskState.DONE

        with patch.object(servicer, '_execute_agent', new_callable=AsyncMock, return_value=mock_result):
            request = MagicMock()
            request.pack_id = "test"
            request.tenant_id = "tenant-456"
            request.input = "Hi"
            request.session_id = ""
            request.idempotency_key = str(uuid.uuid4())
            request.metadata = {}

            context = MockContext(metadata={"trace_id": "trace-xyz-789"})
            responses = []

            async for response in servicer.RunAgent(request, context):
                responses.append(response)

            assert context._trailing_metadata is not None
            # Check that trailing metadata contains correlation fields
            metadata_keys = [m[0] for m in context._trailing_metadata]
            assert "trace_id" in metadata_keys
            assert "tenant_id" in metadata_keys
            assert "task_id" in metadata_keys

    @pytest.mark.asyncio
    async def test_get_agent_status(self):
        servicer = AgentServicer()
        request = MagicMock()
        request.task_id = "task-123"
        request.tenant_id = "tenant-123"

        context = MockContext()
        status = await servicer.GetAgentStatus(request, context)
        assert status.task_id == "task-123"

    @pytest.mark.asyncio
    async def test_cancel_agent(self):
        servicer = AgentServicer()
        request = MagicMock()
        request.task_id = "task-123"
        request.tenant_id = "tenant-123"

        context = MockContext()
        result = await servicer.CancelAgent(request, context)
        assert result.success is True


class TestGrpcServerLifecycle:
    def test_server_config(self):
        from vasini.grpc.server import GrpcServerConfig
        config = GrpcServerConfig(host="0.0.0.0", port=50051)
        assert config.port == 50051

    def test_server_address(self):
        from vasini.grpc.server import GrpcServerConfig
        config = GrpcServerConfig(host="0.0.0.0", port=50051)
        assert f"{config.host}:{config.port}" == "0.0.0.0:50051"
