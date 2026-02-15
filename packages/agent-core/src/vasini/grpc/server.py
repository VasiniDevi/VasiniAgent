"""gRPC server lifecycle management with health service."""

from __future__ import annotations

from dataclasses import dataclass

import grpc
from grpc import aio as grpc_aio

from vasini.agent.v1 import agent_pb2_grpc
from vasini.grpc.servicer import AgentServicer


@dataclass
class GrpcServerConfig:
    host: str = "0.0.0.0"
    port: int = 50051
    max_workers: int = 10


async def create_grpc_server(config: GrpcServerConfig) -> grpc_aio.Server:
    server = grpc_aio.server()

    servicer = AgentServicer()
    agent_pb2_grpc.add_AgentServiceServicer_to_server(servicer, server)

    # Note: gRPC health service requires grpcio-health-checking package
    # which is added to pyproject.toml. Import conditionally to avoid
    # blocking tests if not installed.
    try:
        from grpc_health.v1 import health, health_pb2, health_pb2_grpc

        health_servicer = health.HealthServicer()
        health_servicer.set(
            "vasini.agent.v1.AgentService",
            health_pb2.HealthCheckResponse.SERVING,
        )
        health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)
    except ImportError:
        pass  # grpcio-health-checking not installed

    server.add_insecure_port(f"{config.host}:{config.port}")
    return server


async def serve(config: GrpcServerConfig | None = None) -> None:
    config = config or GrpcServerConfig()
    server = await create_grpc_server(config)
    await server.start()
    print(f"gRPC server listening on {config.host}:{config.port}")
    await server.wait_for_termination()
