import asyncio
import base64
import logging
import os
import time
from http import HTTPStatus
from pathlib import Path
from typing import Final
from uuid import uuid4

import httpx
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from pydantic import ValidationError

from .models import (
    MAX_DURATION_MINS,
    Config,
    LoginResponse,
    OperationMode,
    SetModeRequest,
    TokenCache,
)

logger = logging.getLogger(__name__)


class SigCloudError(Exception):
    """Base exception for SigCloudClient."""

    pass


class SigCloudClient:
    """Client for interacting with Sigen Cloud API."""

    _BASE_URL: Final[str] = "https://api-aus.sigencloud.com"
    _AUTH_URL: Final[str] = f"{_BASE_URL}/auth/oauth/token"
    _MANUAL_MODE_URL: Final[str] = f"{_BASE_URL}/device/energy-profile/instant/manunal"
    _STATION_INFO_URL: Final[str] = f"{_BASE_URL}/device/owner/station/home"
    _CACHE_PATH: Final[Path] = Path(".sig-cloud-control-cache.json")

    # Fixed key and IV used by Sigen Cloud
    _ENCRYPT_KEY: Final[bytes] = (b"s" + b"i" + b"g" + b"e" + b"n") * 3 + b"p"
    _ENCRYPT_IV: Final[bytes] = (b"s" + b"i" + b"g" + b"e" + b"n") * 3 + b"p"
    _CIPHER: Final[Cipher] = Cipher(
        algorithms.AES(_ENCRYPT_KEY),
        modes.CBC(_ENCRYPT_IV),
    )

    def __init__(self, config: Config) -> None:
        """Initialize the client with configuration."""
        self.config = config
        self.client = httpx.AsyncClient()
        self.access_token: str | None = None
        self._station_id: int | None = config.station_id

        # Setup base headers mimicking the app
        self._session_id = str(uuid4())
        self.client.headers.update(
            {
                "accept": "*/*",
                "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
                "auth-client-id": "sigen",
                "client-server": "aus",
                "lang": "en_US",
                "origin": "https://app-aus.sigencloud.com",
                "referer": "https://app-aus.sigencloud.com/",
                "sec-ch-ua": '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"macOS"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "sg-bui": "1",
                "sg-env": "1",
                "sg-pkg": "sigen_app",
                "sg-session": self._session_id,
                "sg-v": "3.4.0",
                "user-agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/145.0.0.0 Safari/537.36"
                ),
            }
        )

    def _get_ts_headers(self) -> dict[str, str]:
        return {
            "sg-log-id": str(uuid4()),
            "sg-ts": str(int(time.time() * 1_000_000)),
        }

    async def _try_login_from_cache(self) -> bool:
        """Attempt to load credentials from the local cache. Returns True if successful."""
        cache = await self._load_cache()
        if not cache:
            return False

        # Recover station_id from cache if we don't have it yet
        if self._station_id is None:
            self._station_id = cache.station_id

        if cache.expires_at > time.time() + 60:  # Valid for at least another minute
            logger.debug("Using cached token")
            self.access_token = cache.access_token
            self.client.headers["authorization"] = f"bearer {self.access_token}"
            return True
        return False

    def _get_login_payload(self) -> dict[str, str]:
        """Prepare the payload for the login request."""
        # Determine password to send
        if self.config.password_encoded:
            password_to_send = self.config.password_encoded
        elif self.config.password:
            password_to_send = self.encrypt_password(self.config.password)
        else:
            # Unreachable due to Config validation
            msg = "Neither password nor password_encoded provided"
            raise SigCloudError(msg)

        return {
            "scope": "server",
            "grant_type": "password",
            "userDeviceId": str(int(time.time() * 1000)),
            "username": self.config.username,
            "password": password_to_send,
        }

    @staticmethod
    def encrypt_password(password: str) -> str:
        """Encrypt a plaintext password using Sigen's AES-128-CBC logic."""
        padder = padding.PKCS7(128).padder()
        padded_data = padder.update(password.encode()) + padder.finalize()

        encryptor = SigCloudClient._CIPHER.encryptor()
        ct = encryptor.update(padded_data) + encryptor.finalize()

        return base64.b64encode(ct).decode()

    async def login(self, use_cache: bool = True) -> None:
        """Authenticate with the Sigen API and store the access token. Checks cache first."""
        if use_cache and await self._try_login_from_cache():
            return

        logger.info("Logging in to Sigen Cloud as %s", self.config.username)
        headers = self._get_ts_headers()
        headers["authorization"] = "Basic c2lnZW46c2lnZW4="
        headers["content-type"] = "application/x-www-form-urlencoded"

        data = self._get_login_payload()

        response = await self.client.post(self._AUTH_URL, headers=headers, data=data)

        if response.status_code != HTTPStatus.OK:
            logger.error("Login failed with status %s: %s", response.status_code, response.text)
            raise SigCloudError(f"Login failed with status {response.status_code}: {response.text}")

        try:
            payload = response.json()
            # Handle potential wrapping or direct payload
            token_data = payload.get("data", payload) if isinstance(payload, dict) else payload
            login_response = LoginResponse.model_validate(token_data)
        except ValidationError as e:
            logger.error("Failed to parse login response: %s", response.text)
            raise SigCloudError(f"Failed to parse login response. Raw payload: {response.text}. Error: {e}") from e
        except Exception as e:
            logger.error("Unexpected error parsing login response: %s", response.text)
            raise SigCloudError(f"Unexpected error parsing login response: {e}. Raw payload: {response.text}") from e

        self.access_token = login_response.access_token
        self.client.headers["authorization"] = f"bearer {self.access_token}"

        # If station_id wasn't provided in config, fetch it
        if self._station_id is None:
            await self._fetch_station_id()

        await self._save_cache(login_response.expires_in_secs)
        logger.info("Successfully logged in and cached token")

    async def _load_cache(self) -> TokenCache | None:
        """Load the token from the cache file if it exists and is valid."""
        try:
            content = await asyncio.to_thread(self._CACHE_PATH.read_text)
            return TokenCache.model_validate_json(content)
        except (FileNotFoundError, ValidationError):
            return None
        except Exception:
            return None

    def _write_cache_file(self, content: str) -> None:
        """Helper to write the cache file securely with restricted permissions."""
        fd = os.open(self._CACHE_PATH, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)

    async def _save_cache(self, expires_in: int) -> None:
        """Save the current token and station ID to the cache file."""
        cache = TokenCache(
            access_token=self.access_token,
            expires_at=time.time() + expires_in,
            station_id=self._station_id,
        )
        content = cache.model_dump_json()
        await asyncio.to_thread(self._write_cache_file, content)

    async def _fetch_station_id(self) -> None:
        """Fetch the station ID from the home info endpoint."""
        logger.debug("Fetching station ID from %s", self._STATION_INFO_URL)
        headers = self._get_ts_headers()
        response = await self.client.get(self._STATION_INFO_URL, headers=headers)
        response.raise_for_status()

        data = response.json()
        if data.get("code") == 0 and "data" in data:
            self._station_id = data["data"].get("stationId")

        if self._station_id is None:
            logger.error("Could not retrieve station ID. Response: %s", response.text)
            raise SigCloudError("Could not retrieve station ID from Sigen Cloud.")
        logger.debug("Fetched station ID: %s", self._station_id)

    async def _set_mode_raw(
        self,
        mode: OperationMode,
        duration: int | None = None,
        power_limitation: float | None = None,
    ) -> None:
        """Directly set the manual mode on the station."""
        if not self.access_token:
            raise SigCloudError("Not logged in. Call login() first.")

        if self._station_id is None:
            raise SigCloudError("Station ID unknown. Login may have failed to retrieve it.")

        request_data = SetModeRequest(
            station_id=self._station_id,
            mode=mode,
            duration=duration,
            power_limitation=power_limitation,
        )
        payload = request_data.model_dump(mode="json", by_alias=True)

        logger.debug("Sending mode update: %s", payload)
        headers = self._get_ts_headers()
        headers["content-type"] = "application/json; charset=utf-8"

        response = await self.client.put(
            self._MANUAL_MODE_URL,
            headers=headers,
            json=payload,
        )
        response.raise_for_status()
        logger.info("Successfully updated mode to %s", mode.name)

    async def _start_mode(
        self,
        mode: OperationMode,
        duration_min: int,
        power_kw: float | None = None,
    ) -> None:
        """Execute the full sequence to start a manual mode."""
        if duration_min <= 0 or duration_min > MAX_DURATION_MINS:
            raise SigCloudError(f"Duration must be between 1 and {MAX_DURATION_MINS} minutes (24 hours).")

        # UI always sends a cancel before starting a new mode
        await self.cancel_self_control()

        await self._set_mode_raw(
            mode=mode,
            duration=duration_min,
            power_limitation=power_kw,
        )

    async def charge_battery(self, duration_min: int, power_kw: float | None = None) -> None:
        """Force charge the battery from the grid."""
        await self._start_mode(OperationMode.CHARGE, duration_min, power_kw)

    async def discharge_battery(self, duration_min: int, power_kw: float | None = None) -> None:
        """Force discharge the battery."""
        await self._start_mode(OperationMode.DISCHARGE, duration_min, power_kw)

    async def hold_battery(self, duration_min: int, power_kw: float | None = None) -> None:
        """Hold the battery at its current SOC."""
        await self._start_mode(OperationMode.HOLD, duration_min, power_kw)

    async def self_consumption(self, duration_min: int, power_kw: float | None = None) -> None:
        """Set to self-consumption mode."""
        await self._start_mode(OperationMode.SELF_CONSUMPTION, duration_min, power_kw)

    async def cancel_self_control(self) -> None:
        """Stop any active manual control."""
        await self._set_mode_raw(mode=OperationMode.CANCEL)

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()
