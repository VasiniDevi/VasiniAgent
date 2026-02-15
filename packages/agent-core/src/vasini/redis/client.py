"""Redis manager with logical DB separation.

DB layout (per design doc):
  - DB 0: cache (short-term memory, session state, rate-limit counters)
  - DB 1: queue (task queue for BullMQ/workers)
  - DB 2: streams (event bus, Redis Streams)

Key patterns:
  - vasini:mem:{tenant_id}:{agent_id}:{key}  — short-term memory
  - vasini:rl:{tenant_id}:{window}           — rate-limit counter

At scale, each role moves to a separate Redis cluster.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import redis.asyncio as aioredis


class RedisRole(Enum):
    CACHE = "cache"      # DB 0: short-term memory + rate-limit
    QUEUE = "queue"      # DB 1: task queue
    STREAMS = "streams"  # DB 2: event streams


@dataclass
class RedisConfig:
    host: str = "localhost"
    port: int = 6379
    password: str | None = None
    db_cache: int = 0
    db_queue: int = 1
    db_streams: int = 2
    max_connections: int = 20


class RedisManager:
    """Manages Redis connections with logical DB separation."""

    _DB_MAP = {
        RedisRole.CACHE: "db_cache",
        RedisRole.QUEUE: "db_queue",
        RedisRole.STREAMS: "db_streams",
    }

    def __init__(self, config: RedisConfig) -> None:
        self.config = config
        self._pools: dict[RedisRole, aioredis.Redis] = {}

    def get_url(self, role: RedisRole) -> str:
        db_num = getattr(self.config, self._DB_MAP[role])
        auth = f":{self.config.password}@" if self.config.password else ""
        return f"redis://{auth}{self.config.host}:{self.config.port}/{db_num}"

    async def get_client(self, role: RedisRole) -> aioredis.Redis:
        if role not in self._pools:
            self._pools[role] = aioredis.from_url(
                self.get_url(role),
                max_connections=self.config.max_connections,
                decode_responses=False,
            )
        return self._pools[role]

    async def _get_client(self, role: RedisRole) -> aioredis.Redis:
        return await self.get_client(role)

    def build_memory_key(self, tenant_id: str, agent_id: str, key: str) -> str:
        return f"vasini:mem:{tenant_id}:{agent_id}:{key}"

    async def memory_set(
        self, tenant_id: str, agent_id: str, key: str, value: str, ttl_seconds: int = 86400
    ) -> None:
        client = await self._get_client(RedisRole.CACHE)
        full_key = self.build_memory_key(tenant_id, agent_id, key)
        await client.set(full_key, value, ex=ttl_seconds)

    async def memory_get(self, tenant_id: str, agent_id: str, key: str) -> bytes | None:
        client = await self._get_client(RedisRole.CACHE)
        full_key = self.build_memory_key(tenant_id, agent_id, key)
        return await client.get(full_key)

    def build_rate_limit_key(self, tenant_id: str, window: str) -> str:
        return f"vasini:rl:{tenant_id}:{window}"

    async def check_rate_limit(
        self, tenant_id: str, window_seconds: int = 60, max_requests: int = 100
    ) -> bool:
        client = await self._get_client(RedisRole.CACHE)
        key = self.build_rate_limit_key(tenant_id, str(window_seconds))
        count = await client.incr(key)
        if count == 1:
            await client.expire(key, window_seconds)
        return count <= max_requests

    async def close(self) -> None:
        for pool in self._pools.values():
            await pool.aclose()
        self._pools.clear()
