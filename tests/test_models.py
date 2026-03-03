import base64
import pytest
from pydantic import ValidationError
from app.models import SetModeRequest, OperationMode, Config


def test_config_valid():
    conf = Config(
        username="user@example.com", password_encoded="MDEyMzQ1Njc4OWFiY2RlZg=="
    )
    assert conf.username == "user@example.com"


def test_config_invalid_email():
    with pytest.raises(ValidationError, match="value is not a valid email address"):
        Config(username="not-an-email", password_encoded="MDEyMzQ1Njc4OWFiY2RlZg==")


def test_config_invalid_password_length():
    # Only 15 bytes decoded
    short_pass = base64.b64encode(b"123456789012345").decode()
    with pytest.raises(
        ValidationError, match="Decoded password must be exactly 16 bytes"
    ):
        Config(username="user@example.com", password_encoded=short_pass)


def test_config_invalid_base64():
    with pytest.raises(
        ValidationError, match="password_encoded must be a valid base64 string"
    ):
        Config(username="user@example.com", password_encoded="!!!not-base64!!!")


def test_config_invalid_station_id():
    with pytest.raises(ValidationError, match="Input should be greater than 0"):
        Config(
            username="user@example.com",
            password_encoded="MDEyMzQ1Njc4OWFiY2RlZg==",
            station_id=0,
        )


def test_set_mode_request_invalid_station_id():
    with pytest.raises(ValidationError, match="Input should be greater than 0"):
        SetModeRequest(station_id=-1, mode=OperationMode.CANCEL)


def test_set_mode_request_valid_cancel():
    req = SetModeRequest(station_id=123, mode=OperationMode.CANCEL)
    assert req.enable is False
    assert req.duration is None
    assert req.power_limitation is None
    # Verify serialisation
    dump = req.model_dump(mode="json", by_alias=True)
    assert dump["enable"] is False
    assert dump["duration"] == ""
    assert dump["powerLimitation"] == ""


def test_set_mode_request_invalid_cancel_with_duration():
    with pytest.raises(
        ValidationError,
        match="duration and power_limitation must be null/None when mode is CANCEL",
    ):
        SetModeRequest(station_id=123, mode=OperationMode.CANCEL, duration=30)


def test_set_mode_request_valid_charge():
    req = SetModeRequest(
        station_id=123, mode=OperationMode.CHARGE, duration=60, power_limitation=2.5
    )
    assert req.enable is True
    assert req.duration == 60
    assert req.power_limitation == 2.5
    # Verify serialisation
    dump = req.model_dump(mode="json", by_alias=True)
    assert dump["enable"] is True
    assert dump["duration"] == "60"
    assert dump["powerLimitation"] == "2.5"


def test_set_mode_request_invalid_charge_no_duration():
    with pytest.raises(ValidationError, match="duration is required for mode CHARGE"):
        SetModeRequest(station_id=123, mode=OperationMode.CHARGE)


def test_set_mode_request_invalid_charge_out_of_range():
    with pytest.raises(
        ValidationError, match="duration must be between 1 and 1440 minutes"
    ):
        SetModeRequest(station_id=123, mode=OperationMode.CHARGE, duration=1441)


def test_set_mode_request_invalid_charge_negative_power():
    with pytest.raises(
        ValidationError, match="power_limitation must be a positive number"
    ):
        SetModeRequest(
            station_id=123,
            mode=OperationMode.CHARGE,
            duration=60,
            power_limitation=-1.0,
        )
    with pytest.raises(
        ValidationError, match="power_limitation must be a positive number"
    ):
        SetModeRequest(
            station_id=123, mode=OperationMode.CHARGE, duration=60, power_limitation=0.0
        )


def test_set_mode_request_invalid_charge_excessive_power():
    with pytest.raises(ValidationError, match="exceeds sanity limit of 100 kW"):
        SetModeRequest(
            station_id=123,
            mode=OperationMode.CHARGE,
            duration=60,
            power_limitation=100.1,
        )


def test_set_mode_request_invalid_hold_with_power():
    with pytest.raises(
        ValidationError, match="power_limitation is not supported for mode HOLD"
    ):
        SetModeRequest(
            station_id=123, mode=OperationMode.HOLD, duration=60, power_limitation=1.0
        )


def test_set_mode_request_invalid_self_consumption_with_power():
    with pytest.raises(
        ValidationError,
        match="power_limitation is not supported for mode SELF_CONSUMPTION",
    ):
        SetModeRequest(
            station_id=123,
            mode=OperationMode.SELF_CONSUMPTION,
            duration=60,
            power_limitation=1.0,
        )
