"""FastAPI application -- entry point for the admin API."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from admin_api.routes import (
    agent,
    config,
    dashboard,
    messages,
    monitoring,
    moods,
    users,
)

app = FastAPI(
    title="Wellness Admin API",
    version="0.1.0",
    description="Backend API for the Vasini Wellness admin dashboard.",
)

# CORS -- allow the local dev frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers
app.include_router(dashboard.router)
app.include_router(users.router)
app.include_router(messages.router)
app.include_router(moods.router)
app.include_router(agent.router)
app.include_router(monitoring.router)
app.include_router(config.router)


@app.get("/health")
async def health():
    """Unauthenticated health-check endpoint."""
    return {"status": "ok"}
