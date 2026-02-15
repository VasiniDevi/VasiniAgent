"""Tenant context management for RLS enforcement.

Every database operation MUST:
1. Be inside an explicit transaction (BEGIN/COMMIT)
2. Call set_tenant_context() at the start of the transaction
3. SET LOCAL app.tenant_id = '<uuid>'

PgBouncer: transaction pooling mode — SET LOCAL is scoped to transaction.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class TenantContext:
    tenant_id: str


async def set_tenant_context(session: AsyncSession, tenant_id: str) -> None:
    """Set tenant context for RLS enforcement within current transaction.

    Uses SET LOCAL so the setting is scoped to the current transaction
    and compatible with PgBouncer transaction pooling.
    """
    await session.execute(
        text("SET LOCAL app.tenant_id = :tenant_id"),
        {"tenant_id": tenant_id},
    )
