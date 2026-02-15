"""Token usage monitoring endpoints."""
from __future__ import annotations

import time

import aiosqlite
from fastapi import APIRouter, Depends, Query

from admin_api.auth import verify_token
from admin_api.deps import get_db

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])

# Model cost per 1 million tokens (USD)
MODEL_COSTS: dict[str, dict[str, float]] = {
    "sonnet": {"input": 3.0, "output": 15.0},
    "opus": {"input": 15.0, "output": 75.0},
}


def _model_family(model_name: str) -> str:
    """Map a full model identifier to a cost family."""
    lower = model_name.lower()
    if "opus" in lower:
        return "opus"
    # Default to sonnet for any sonnet / haiku / unknown models
    return "sonnet"


def _calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Compute the USD cost for a given token usage record."""
    family = _model_family(model)
    costs = MODEL_COSTS.get(family, MODEL_COSTS["sonnet"])
    return (input_tokens * costs["input"] + output_tokens * costs["output"]) / 1_000_000


@router.get("/tokens", dependencies=[Depends(verify_token)])
async def token_usage(
    days: int = Query(default=30, ge=1, le=365),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Return per-record token usage with cost calculations."""
    since = time.time() - days * 86400
    cur = await db.execute(
        "SELECT id, user_id, model, input_tokens, output_tokens, created_at "
        "FROM token_usage WHERE created_at >= ? ORDER BY created_at DESC",
        (since,),
    )
    rows = await cur.fetchall()

    records = []
    total_cost = 0.0
    total_input = 0
    total_output = 0
    for r in rows:
        cost = _calculate_cost(r[2], r[3], r[4])
        total_cost += cost
        total_input += r[3]
        total_output += r[4]
        records.append(
            {
                "id": r[0],
                "user_id": r[1],
                "model": r[2],
                "input_tokens": r[3],
                "output_tokens": r[4],
                "cost_usd": round(cost, 6),
                "created_at": r[5],
            }
        )

    return {
        "days": days,
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "total_cost_usd": round(total_cost, 4),
        "records": records,
    }


@router.get("/summary", dependencies=[Depends(verify_token)])
async def token_summary(db: aiosqlite.Connection = Depends(get_db)):
    """Return aggregated token usage for today / 7 days / 30 days."""
    now = time.time()
    periods = {
        "today": now - 86400,
        "week": now - 7 * 86400,
        "month": now - 30 * 86400,
    }

    result: dict = {}
    for label, since in periods.items():
        cur = await db.execute(
            "SELECT model, COALESCE(SUM(input_tokens), 0), COALESCE(SUM(output_tokens), 0) "
            "FROM token_usage WHERE created_at >= ? GROUP BY model",
            (since,),
        )
        rows = await cur.fetchall()
        total_input = 0
        total_output = 0
        total_cost = 0.0
        by_model: list[dict] = []
        for r in rows:
            cost = _calculate_cost(r[0], r[1], r[2])
            total_input += r[1]
            total_output += r[2]
            total_cost += cost
            by_model.append(
                {
                    "model": r[0],
                    "input_tokens": r[1],
                    "output_tokens": r[2],
                    "cost_usd": round(cost, 6),
                }
            )
        result[label] = {
            "input_tokens": total_input,
            "output_tokens": total_output,
            "cost_usd": round(total_cost, 4),
            "by_model": by_model,
        }

    return result
