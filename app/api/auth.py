"""API key authentication dependency."""

from typing import Optional

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.config import settings

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _get_valid_api_keys() -> set[str]:
    """Parse the API_KEYS env var into a set of valid keys."""
    if not settings.api_keys:
        return set()
    return {k.strip() for k in settings.api_keys.split(",") if k.strip()}


async def verify_api_key(
    api_key: Optional[str] = Security(_api_key_header),
) -> Optional[str]:
    """Validate the X-API-Key header.

    If API_KEYS is empty/unset, authentication is disabled (open access).
    If API_KEYS is set, the header must contain a valid key.
    """
    valid_keys = _get_valid_api_keys()
    if not valid_keys:
        return None
    if not api_key or api_key not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return api_key
