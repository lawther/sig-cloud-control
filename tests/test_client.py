from unittest.mock import patch, MagicMock

import pytest
import httpx
from app.client import SigenClient, SigenError
from app.models import Config, OperationMode


@pytest.fixture
def config():
    # 'MDEyMzQ1Njc4OWFiY2RlZg==' is exactly 16 bytes decoded
    return Config(
        username="test@example.com",
        password_encoded="MDEyMzQ1Njc4OWFiY2RlZg==",
        station_id=12345,
    )


@pytest.fixture
def client(config):
    return SigenClient(config)


@pytest.mark.asyncio
async def test_login_success(client):
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
        patch.object(
            httpx.AsyncClient, "post", return_value=mock_response
        ) as mock_post,
        patch.object(SigenClient, "_save_cache"),
        patch.object(SigenClient, "_load_cache", return_value=None),
    ):
        await client.login()

        assert client.access_token == "fake_token"
        assert client.client.headers["authorization"] == "bearer fake_token"

        # Verify the call
        args, kwargs = mock_post.call_args
        assert kwargs["data"]["username"] == "test@example.com"
        assert kwargs["data"]["password"] == "MDEyMzQ1Njc4OWFiY2RlZg=="


@pytest.mark.asyncio
async def test_start_mode_calls_cancel_first(client):
    client.access_token = "fake_token"
    client.client.headers["authorization"] = "bearer fake_token"

    # Mock the PUT response
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.status_code = 200

    with patch.object(httpx.AsyncClient, "put", return_value=mock_response) as mock_put:
        await client.charge_battery(60, power_kw=2.5)

        # Should have 2 PUT calls: one for cancel, one for charge
        assert mock_put.call_count == 2

        # First call should be cancel (enable=False)
        cancel_args, cancel_kwargs = mock_put.call_args_list[0]
        cancel_data = cancel_kwargs["json"]
        assert cancel_data["enable"] is False
        assert cancel_data["mode"] == OperationMode.CANCEL.value
        assert cancel_data["duration"] == ""
        assert cancel_data["powerLimitation"] == ""

        # Second call should be charge (enable=True)
        charge_args, charge_kwargs = mock_put.call_args_list[1]
        charge_data = charge_kwargs["json"]
        assert charge_data["enable"] is True
        assert charge_data["mode"] == OperationMode.CHARGE.value
        assert charge_data["duration"] == "60"
        assert charge_data["powerLimitation"] == "2.5"


@pytest.mark.asyncio
async def test_invalid_duration_raises_error(client):
    client.access_token = "fake_token"
    with pytest.raises(SigenError, match="Duration must be between 1 and 1440"):
        await client.charge_battery(0)

    with pytest.raises(SigenError, match="Duration must be between 1 and 1440"):
        await client.charge_battery(1441)
