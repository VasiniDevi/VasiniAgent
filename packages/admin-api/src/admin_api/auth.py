"""Bearer token authentication."""
from __future__ import annotations

import os

from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

security = HTTPBearer()
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "dev-token-change-me")


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> str:
    """Validate the Bearer token against the configured ADMIN_TOKEN."""
    if credentials.credentials != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
    return credentials.credentials
