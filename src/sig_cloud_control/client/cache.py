import asyncio
import os
import time
from pathlib import Path
from typing import Final

from platformdirs import user_cache_path
from pydantic import ValidationError

from ..models import TokenCache

_DEFAULT_CACHE_PATH: Final[Path] = user_cache_path("sig-cloud-control") / "token-cache.json"


async def load_cache(cache_path: Path | None) -> TokenCache | None:
    """Load the token from the cache file if it exists and is valid."""
    if cache_path is None:
        return None
    try:
        content = await asyncio.to_thread(cache_path.read_text)
        return TokenCache.model_validate_json(content)
    except (FileNotFoundError, ValidationError):
        return None
    except Exception:
        return None


def _write_cache_file(cache_path: Path, content: str) -> None:
    """Helper to write the cache file securely with restricted permissions."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(cache_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)


async def save_cache(
    cache_path: Path | None,
    access_token: str | None,
    expires_in_secs: int,
    station_id: int | None,
) -> None:
    """Save the current token and station ID to the cache file."""
    if cache_path is None or access_token is None:
        return
    cache = TokenCache(
        access_token=access_token,
        expires_at=time.time() + expires_in_secs,
        station_id=station_id,
    )
    content = cache.model_dump_json()
    await asyncio.to_thread(_write_cache_file, cache_path, content)
