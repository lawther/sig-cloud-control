from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from sig_cloud_control.client import SigCloudClient, SigCloudError
from sig_cloud_control.models import Config, OperationMode


@pytest.fixture
def config() -> Config:
    # 'MDEyMzQ1Njc4OWFiY2RlZg==' is exactly 16 bytes decoded
    return Config(
        username="test@example.com",
        password_encoded="MDEyMzQ1Njc4OWFiY2RlZg==",
        station_id=12345,
    )


@pytest.fixture
def client(config: Config) -> SigCloudClient:
    return SigCloudClient(config)


def test_encrypt_password() -> None:
    password = "Sigen12345!"
    expected = "rV6FkNoIMt8nyDRbAUH/aw=="
    assert SigCloudClient.encrypt_password(password) == expected


@pytest.mark.asyncio
async def test_set_mode_station_id_unknown(client: SigCloudClient) -> None:
    client.access_token = "fake_token"
    client._station_id = None
    with pytest.raises(SigCloudError, match=r"Station ID unknown. Login may have failed to retrieve it."):
        await client.charge_battery(60)


@pytest.mark.asyncio
async def test_set_mode_not_logged_in(client: SigCloudClient) -> None:
    client.access_token = None
    with pytest.raises(SigCloudError, match=r"Not logged in. Call login\(\) first."):
        await client.charge_battery(60)


@pytest.mark.asyncio
async def test_login_success(client: SigCloudClient) -> None:
    # Mock response for login
    # We use MagicMock for the response because json() and raise_for_status() are sync in httpx
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "fake_token",
        "token_type": "bearer",
        "expires_in": 3600,
    }

    with (
        patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_response) as mock_post,
        patch.object(SigCloudClient, "_save_cache", new_callable=AsyncMock),
        patch.object(SigCloudClient, "_load_cache", new_callable=AsyncMock, return_value=None),
    ):
        await client.login()

        assert client.access_token == "fake_token"
        assert client.client.headers["authorization"] == "bearer fake_token"

        # Verify the call
        _args, kwargs = mock_post.call_args
        assert kwargs["data"]["username"] == "test@example.com"
        assert kwargs["data"]["password"] == "MDEyMzQ1Njc4OWFiY2RlZg=="


@pytest.mark.asyncio
async def test_start_mode_calls_cancel_first(client: SigCloudClient) -> None:
    client.access_token = "fake_token"
    client.client.headers["authorization"] = "bearer fake_token"

    # Mock the PUT response
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200

    with patch.object(httpx.AsyncClient, "put", new_callable=AsyncMock, return_value=mock_response) as mock_put:
        await client.charge_battery(60, power_kw=2.5)

        # Should have 2 PUT calls: one for cancel, one for charge
        expected_call_count = 2
        assert mock_put.call_count == expected_call_count

        # First call should be cancel (enable=False)
        _cancel_args, cancel_kwargs = mock_put.call_args_list[0]
        cancel_data = cancel_kwargs["json"]
        assert cancel_data["enable"] is False
        assert cancel_data["mode"] == OperationMode.CANCEL.value
        assert cancel_data["duration"] == ""
        assert cancel_data["powerLimitation"] == ""

        # Second call should be charge (enable=True)
        _charge_args, charge_kwargs = mock_put.call_args_list[1]
        charge_data = charge_kwargs["json"]
        assert charge_data["enable"] is True
        assert charge_data["mode"] == OperationMode.CHARGE.value
        assert charge_data["duration"] == "60"
        assert charge_data["powerLimitation"] == "2.5"


@pytest.mark.asyncio
async def test_invalid_duration_raises_error(client: SigCloudClient) -> None:
    client.access_token = "fake_token"
    with pytest.raises(SigCloudError, match="Duration must be between 1 and 1440"):
        await client.charge_battery(0)

    with pytest.raises(SigCloudError, match="Duration must be between 1 and 1440"):
        await client.charge_battery(1441)


@pytest.mark.asyncio
async def test_login_failure(client: SigCloudClient) -> None:
    # Mock response for failed login (e.g., 401 Unauthorized)
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 401
    mock_response.text = "Unauthorized"

    with (
        patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_response),
        patch.object(SigCloudClient, "_load_cache", new_callable=AsyncMock, return_value=None),
        pytest.raises(SigCloudError, match="Login failed with status 401: Unauthorized"),
    ):
        await client.login()


@pytest.mark.asyncio
async def test_login_invalid_json_payload(client: SigCloudClient) -> None:
    # Mock response for login with 200 OK but invalid JSON payload
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_response.text = "invalid_json_here"

    with (
        patch.object(httpx.AsyncClient, "post", new_callable=AsyncMock, return_value=mock_response),
        patch.object(SigCloudClient, "_load_cache", new_callable=AsyncMock, return_value=None),
        pytest.raises(SigCloudError, match="Unexpected error parsing login response"),
    ):
        await client.login()


@pytest.mark.asyncio
async def test_cache_disabled(config: Config) -> None:
    client = SigCloudClient(config, cache_path=None)
    assert client.cache_path is None

    with patch.object(SigCloudClient, "_load_cache", wraps=client._load_cache) as mock_load:
        assert await client._try_login_from_cache() is False
        mock_load.assert_not_called()

    with patch.object(SigCloudClient, "_write_cache_file", wraps=client._write_cache_file) as mock_write:
        await client._save_cache(3600)
        mock_write.assert_not_called()


def test_get_login_payload_no_password() -> None:
    # Use model_construct to bypass Pydantic validation
    config = Config.model_construct(username="test@example.com")
    client = SigCloudClient(config)
    with pytest.raises(SigCloudError, match="Neither password nor password_encoded provided"):
        client._get_login_payload()
