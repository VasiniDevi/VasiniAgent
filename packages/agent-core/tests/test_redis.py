"""Tests for Redis client with logical DB separation and rate limiting."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from vasini.redis.client import (
    RedisConfig,
    RedisManager,
    RedisRole,
)


class TestRedisConfig:
    def test_default_config(self):
        config = RedisConfig()
        assert config.host == "localhost"
        assert config.port == 6379
        assert config.db_cache == 0
        assert config.db_queue == 1
        assert config.db_streams == 2

    def test_custom_config(self):
        config = RedisConfig(host="redis.prod", port=6380)
        assert config.host == "redis.prod"
        assert config.port == 6380


class TestRedisManager:
    def test_create_manager(self):
        config = RedisConfig()
        manager = RedisManager(config)
        assert manager.config.host == "localhost"

    def test_get_url_for_cache(self):
        config = RedisConfig()
        manager = RedisManager(config)
        url = manager.get_url(RedisRole.CACHE)
        assert "localhost" in url
        assert "/0" in url

    def test_get_url_for_queue(self):
        config = RedisConfig()
        manager = RedisManager(config)
        url = manager.get_url(RedisRole.QUEUE)
        assert "/1" in url

    def test_get_url_for_streams(self):
        config = RedisConfig()
        manager = RedisManager(config)
        url = manager.get_url(RedisRole.STREAMS)
        assert "/2" in url

    def test_pool_per_role(self):
        config = RedisConfig()
        manager = RedisManager(config)
        cache_url = manager.get_url(RedisRole.CACHE)
        queue_url = manager.get_url(RedisRole.QUEUE)
        assert cache_url != queue_url

    @pytest.mark.asyncio
    async def test_short_term_memory_set_get(self):
        config = RedisConfig()
        manager = RedisManager(config)

        mock_redis = AsyncMock()
        mock_redis.set = AsyncMock(return_value=True)
        mock_redis.get = AsyncMock(return_value=b'{"key": "value"}')

        with patch.object(manager, '_get_client', return_value=mock_redis):
            await manager.memory_set("tenant-1", "agent-1", "ctx:123", '{"key": "value"}', ttl_seconds=86400)
            mock_redis.set.assert_called_once()

            result = await manager.memory_get("tenant-1", "agent-1", "ctx:123")
            assert result == b'{"key": "value"}'

    def test_memory_key_includes_tenant(self):
        config = RedisConfig()
        manager = RedisManager(config)
        key = manager.build_memory_key("tenant-abc", "agent-1", "ctx:session")
        assert "tenant-abc" in key
        assert "agent-1" in key


class TestRateLimiting:
    def test_rate_limit_key_format(self):
        config = RedisConfig()
        manager = RedisManager(config)
        key = manager.build_rate_limit_key("tenant-123", "60")
        assert key == "vasini:rl:tenant-123:60"

    @pytest.mark.asyncio
    async def test_check_rate_limit_under_limit(self):
        config = RedisConfig()
        manager = RedisManager(config)

        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock(return_value=True)

        with patch.object(manager, '_get_client', return_value=mock_redis):
            allowed = await manager.check_rate_limit("tenant-123", window_seconds=60, max_requests=100)
            assert allowed is True

    @pytest.mark.asyncio
    async def test_check_rate_limit_over_limit(self):
        config = RedisConfig()
        manager = RedisManager(config)

        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=101)
        mock_redis.expire = AsyncMock(return_value=True)

        with patch.object(manager, '_get_client', return_value=mock_redis):
            allowed = await manager.check_rate_limit("tenant-123", window_seconds=60, max_requests=100)
            assert allowed is False

    @pytest.mark.asyncio
    async def test_rate_limit_sets_ttl_on_first_request(self):
        config = RedisConfig()
        manager = RedisManager(config)

        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(return_value=1)
        mock_redis.expire = AsyncMock(return_value=True)

        with patch.object(manager, '_get_client', return_value=mock_redis):
            await manager.check_rate_limit("tenant-123", window_seconds=60, max_requests=100)
            mock_redis.expire.assert_called_once()
