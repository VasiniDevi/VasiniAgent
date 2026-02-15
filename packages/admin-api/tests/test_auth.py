"""Tests for authentication and the health endpoint."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from admin_api.app import app


@pytest.fixture
async def client():
    """Async HTTP client wired to the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_no_auth(client: AsyncClient):
    """GET /health should return 200 without authentication."""
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_dashboard_requires_auth(client: AsyncClient):
    """GET /api/dashboard without a token should be rejected (401 or 403)."""
    resp = await client.get("/api/dashboard")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_dashboard_rejects_bad_token(client: AsyncClient):
    """GET /api/dashboard with an invalid token should return 401."""
    resp = await client.get(
        "/api/dashboard",
        headers={"Authorization": "Bearer wrong-token"},
    )
    assert resp.status_code == 401
