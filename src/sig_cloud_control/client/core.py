import logging
import time
from http import HTTPStatus
from pathlib import Path
from uuid import uuid4

import httpx
from pydantic import ValidationError

from .._encryption import encrypt_password
from ..models import (
    MAX_DURATION_MINS,
    Config,
    LoginResponse,
    OperationMode,
    SetModeRequest,
)
from .cache import _DEFAULT_CACHE_PATH, load_cache, save_cache
from .exceptions import APIError, AuthenticationError, SigCloudError, StationError

logger = logging.getLogger(__name__)


class SigCloudClient:
    """Client for interacting with Sigen Cloud API."""

    def __init__(self, config: Config, cache_path: Path | None = _DEFAULT_CACHE_PATH) -> None:
        """Initialize the client with configuration."""
        self.config = config
        self.cache_path = cache_path
        self.client = httpx.AsyncClient()
        self.access_token: str | None = None
        self._station_id: int | None = config.station_id

        _base_url = f"https://api-{config.region.value}.sigencloud.com"
        self._auth_url = f"{_base_url}/auth/oauth/token"
        self._manual_mode_url = f"{_base_url}/device/energy-profile/instant/manunal"
        self._station_info_url = f"{_base_url}/device/owner/station/home"

        # Setup base headers mimicking the app
        self._session_id = str(uuid4())
        self.client.headers.update(
            {
                "accept": "*/*",
                "accept-language": "en-GB,en-US;q=0.9,en;q=0.8",
                "auth-client-id": "sigen",
                "client-server": config.region.value,
                "lang": "en_US",
                "origin": f"https://app-{config.region.value}.sigencloud.com",
                "referer": f"https://app-{config.region.value}.sigencloud.com/",
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

    async def __aenter__(self) -> "SigCloudClient":
        """Enter the async context manager."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Exit the async context manager and close the HTTP client."""
        await self.aclose()

    def _get_ts_headers(self) -> dict[str, str]:
        return {
            "sg-log-id": str(uuid4()),
            "sg-ts": str(int(time.time() * 1_000_000)),
        }

    async def _try_login_from_cache(self) -> bool:
        """Attempt to load credentials from the local cache. Returns True if successful."""
        if self.cache_path is None:
            return False

        cache = await load_cache(self.cache_path)
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
        if self.config.password_encoded:
            password_to_send = self.config.password_encoded
        elif self.config.password:
            password_to_send = encrypt_password(self.config.password)
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

    async def login(self, use_cache: bool = True) -> None:
        """Authenticate with the Sigen API and store the access token. Checks cache first."""
        if use_cache and await self._try_login_from_cache():
            return

        logger.info("Logging in to Sigen Cloud as %s", self.config.username)
        headers = self._get_ts_headers()
        headers["authorization"] = "Basic c2lnZW46c2lnZW4="
        headers["content-type"] = "application/x-www-form-urlencoded"

        data = self._get_login_payload()

        response = await self.client.post(self._auth_url, headers=headers, data=data)

        if response.status_code != HTTPStatus.OK:
            logger.error("Login failed with status %s: %s", response.status_code, response.text)
            raise AuthenticationError(f"Login failed with status {response.status_code}: {response.text}")

        try:
            payload = response.json()
            # Handle potential wrapping or direct payload
            token_data = payload.get("data", payload) if isinstance(payload, dict) else payload
            login_response = LoginResponse.model_validate(token_data)
        except ValidationError as e:
            logger.error("Failed to parse login response: %s", response.text)
            raise APIError(f"Failed to parse login response. Raw payload: {response.text}. Error: {e}") from e
        except Exception as e:
            logger.error("Unexpected error parsing login response: %s", response.text)
            raise APIError(f"Unexpected error parsing login response: {e}. Raw payload: {response.text}") from e

        self.access_token = login_response.access_token
        self.client.headers["authorization"] = f"bearer {self.access_token}"

        # If station_id wasn't provided in config, fetch it
        if self._station_id is None:
            await self._fetch_station_id()

        await save_cache(
            self.cache_path,
            self.access_token,
            login_response.expires_in_secs,
            self._station_id,
        )
        logger.info("Successfully logged in and cached token")

    async def _fetch_station_id(self) -> None:
        """Fetch the station ID from the home info endpoint."""
        logger.debug("Fetching station ID from %s", self._station_info_url)
        headers = self._get_ts_headers()
        response = await self.client.get(self._station_info_url, headers=headers)
        response.raise_for_status()

        data = response.json()
        if data.get("code") == 0 and "data" in data:
            self._station_id = data["data"].get("stationId")

        if self._station_id is None:
            logger.error("Could not retrieve station ID. Response: %s", response.text)
            raise StationError("Could not retrieve station ID from Sigen Cloud.")
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
            raise StationError("Station ID unknown. Login may have failed to retrieve it.")

        request_data = SetModeRequest(
            station_id=self._station_id,
            mode=mode,
            duration=duration,
            power_limitation=power_limitation,
        )

        logger.debug("Sending mode update: %s", request_data.model_dump(by_alias=True))
        headers = self._get_ts_headers()
        headers["content-type"] = "application/json; charset=utf-8"

        response = await self.client.put(
            self._manual_mode_url,
            headers=headers,
            json=request_data.model_dump(mode="json", by_alias=True),
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

    async def hold_battery(self, duration_min: int) -> None:
        """Hold the battery at its current SOC."""
        await self._start_mode(OperationMode.HOLD, duration_min)

    async def self_consumption(self, duration_min: int) -> None:
        """Set to self-consumption mode."""
        await self._start_mode(OperationMode.SELF_CONSUMPTION, duration_min)

    async def cancel_self_control(self) -> None:
        """Stop any active manual control."""
        await self._set_mode_raw(mode=OperationMode.CANCEL)

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self.client.aclose()
