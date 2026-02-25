"""Audit logger — persists decision logs and metrics to the database."""

from __future__ import annotations

import json

import aiosqlite


class AuditLogger:
    """Persists coaching pipeline decision logs and safety events.

    Each method commits after insert so downstream consumers
    can observe changes immediately.
    """

    def __init__(self, db: aiosqlite.Connection) -> None:
        self._db = db

    async def log_decision(
        self,
        session_id: str,
        context_state: dict,
        decision: str,
        opportunity_score: float,
        selected_practice_id: str | None,
        latency_ms: int,
        cost: float,
    ) -> None:
        """Insert a coaching decision into *decision_logs*."""
        await self._db.execute(
            "INSERT INTO decision_logs "
            "(session_id, context_state_json, decision, "
            "opportunity_score, selected_practice_id, latency_ms, cost) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                json.dumps(context_state),
                decision,
                opportunity_score,
                selected_practice_id,
                latency_ms,
                cost,
            ),
        )
        await self._db.commit()

    async def log_safety_event(
        self,
        session_id: str,
        detector: str,
        severity: str,
        action: str,
        message_hash: str | None = None,
    ) -> None:
        """Insert a safety event into *safety_events*."""
        await self._db.execute(
            "INSERT INTO safety_events "
            "(session_id, detector, severity, action, message_hash) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, detector, severity, action, message_hash),
        )
        await self._db.commit()

    async def get_metrics(self) -> dict:
        """Return aggregate metrics from *decision_logs*.

        Returns a dict with keys:
        - total_decisions: total number of logged decisions
        - suggest_count: number of 'suggest' decisions
        - avg_latency_ms: average latency rounded to 1 decimal (None if no rows)
        """
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM decision_logs"
        )
        total_decisions = (await cursor.fetchone())[0]

        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM decision_logs WHERE decision = 'suggest'"
        )
        suggest_count = (await cursor.fetchone())[0]

        cursor = await self._db.execute(
            "SELECT AVG(latency_ms) FROM decision_logs"
        )
        avg_raw = (await cursor.fetchone())[0]
        avg_latency_ms = round(avg_raw, 1) if avg_raw is not None else None

        return {
            "total_decisions": total_decisions,
            "suggest_count": suggest_count,
            "avg_latency_ms": avg_latency_ms,
        }
