import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from sig_cloud_control.client import SigCloudClient
from sig_cloud_control.models import Config, TokenCache

MOCK_STATION_ID_1 = 98765
MOCK_STATION_ID_2 = 55555
MOCK_STATION_ID_3 = 11111


@pytest.fixture
def config_no_station() -> Config:
    return Config(
        username="test@example.com",
        password_encoded="MDEyMzQ1Njc4OWFiY2RlZg==",
    )


@pytest.mark.asyncio
async def test_fetch_station_id_success(config_no_station: Config) -> None:
    client = SigCloudClient(config_no_station)

    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {"code": 0, "data": {"stationId": MOCK_STATION_ID_1}}

    with patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=mock_response) as mock_get:
        await client._fetch_station_id()
        assert client._station_id == MOCK_STATION_ID_1
        mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_try_login_from_cache_recovers_station_id_even_if_expired(config_no_station: Config) -> None:
    client = SigCloudClient(config_no_station)
    assert client._station_id is None

    # Mock an expired cache that has a station_id
    expired_cache = TokenCache(
        access_token="expired_token",
        expires_at=time.time() - 3600,
        station_id=MOCK_STATION_ID_2,
    )

    with patch.object(SigCloudClient, "_load_cache", new_callable=AsyncMock, return_value=expired_cache):
        # Should return False because token is expired
        result = await client._try_login_from_cache()
        assert result is False
        # BUT station_id should have been recovered
        assert client._station_id == MOCK_STATION_ID_2


@pytest.mark.asyncio
async def test_login_skips_fetch_if_station_id_in_cache(config_no_station: Config) -> None:
    client = SigCloudClient(config_no_station)

    # 1. First login (no cache)
    login_response = MagicMock(spec=httpx.Response)
    login_response.status_code = 200
    login_response.json.return_value = {
        "access_token": "token1",
        "token_type": "bearer",
        "expires_in": 3600,
    }

    station_response = MagicMock(spec=httpx.Response)
    station_response.status_code = 200
    station_response.json.return_value = {"code": 0, "data": {"stationId": MOCK_STATION_ID_3}}

    with (
        patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=login_response),
        patch.object(
            httpx.AsyncClient, "get", new_callable=AsyncMock, return_value=station_response
        ) as mock_get_station,
        patch.object(SigCloudClient, "_load_cache", new_callable=AsyncMock, return_value=None),
        patch.object(SigCloudClient, "_save_cache", new_callable=AsyncMock) as mock_save,
    ):
        await client.login()
        assert client._station_id == MOCK_STATION_ID_3
        mock_get_station.assert_called_once()
        mock_save.assert_called_once()

    # 2. Second login (expired cache with station_id)
    client._station_id = None  # Reset for test
    expired_cache = TokenCache(
        access_token="token1",
        expires_at=time.time() - 10,  # Expired
        station_id=MOCK_STATION_ID_3,
    )

    with (
        patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=login_response),
        patch.object(httpx.AsyncClient, "get", new_callable=AsyncMock) as mock_get_station_2,
        patch.object(SigCloudClient, "_load_cache", new_callable=AsyncMock, return_value=expired_cache),
        patch.object(SigCloudClient, "_save_cache", new_callable=AsyncMock),
    ):
        await client.login()
        assert client._station_id == MOCK_STATION_ID_3
        # Should NOT have called get station info again!
        mock_get_station_2.assert_not_called()
