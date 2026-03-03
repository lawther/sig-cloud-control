import base64
from enum import StrEnum
from typing import Final, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

PASSWORD_LEN_BYTES: Final[int] = 16
MAX_DURATION_MINS: Final[int] = 1440
MAX_POWER_LIMIT_KW: Final[float] = 100.0


class Config(BaseModel):
    model_config = ConfigDict(strict=True)

    username: EmailStr
    """The user's Sigen Cloud email address."""

    password: str | None = None
    """The user's plaintext password (will be encoded automatically)."""

    password_encoded: str | None = None
    """The base64 encoded/encrypted password from the browser."""

    station_id: int | None = Field(default=None, gt=0)
    """Optional station ID. Must be positive if provided."""

    @model_validator(mode="after")
    def validate_password_source(self) -> Self:
        if self.password is None and self.password_encoded is None:
            raise ValueError("Either 'password' or 'password_encoded' must be provided")
        return self

    @field_validator("password_encoded")
    @classmethod
    def validate_password_encoded(cls, v: str | None) -> str | None:
        if v is None:
            return None
        try:
            decoded = base64.b64decode(v, validate=True)
            if len(decoded) != PASSWORD_LEN_BYTES:
                raise ValueError(f"Decoded password must be exactly {PASSWORD_LEN_BYTES} bytes, got {len(decoded)}")
        except Exception as e:
            if isinstance(e, ValueError) and f"{PASSWORD_LEN_BYTES} bytes" in str(e):
                raise
            raise ValueError("password_encoded must be a valid base64 string") from e
        return v


class LoginResponse(BaseModel):
    """Standard OAuth 2.0 Access Token Response (RFC 6749, Section 5.1)."""

    access_token: str
    """The access token issued by the authorisation server."""

    refresh_token: str | None = None
    """The refresh token, which can be used to obtain new access tokens."""

    token_type: str
    """The type of the token issued, e.g., 'bearer'."""

    expires_in_secs: int = Field(alias="expires_in")
    """The lifetime in seconds of the access token."""


class TokenCache(BaseModel):
    access_token: str
    expires_at: float  # Absolute timestamp
    station_id: int | None = Field(default=None, gt=0)


class OperationMode(StrEnum):
    CHARGE = "0"
    DISCHARGE = "1"
    HOLD = "2"
    SELF_CONSUMPTION = "3"
    CANCEL = ""


class SetModeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    mode: OperationMode
    station_id: int = Field(alias="stationId", gt=0)
    duration: int | None = None
    power_limitation: float | None = Field(default=None, alias="powerLimitation")
    enable: bool = False

    @field_serializer("duration", "power_limitation")
    def serialise_to_str(self, v: int | float | None) -> str:
        return str(v) if v is not None else ""

    @model_validator(mode="after")
    def validate_duration_and_power(self) -> Self:
        self.enable = self.mode != OperationMode.CANCEL

        match self.mode:
            case OperationMode.CANCEL:
                if self.duration is not None or self.power_limitation is not None:
                    raise ValueError("duration and power_limitation must be null/None when mode is CANCEL")

            case OperationMode.CHARGE | OperationMode.DISCHARGE:
                self._validate_duration()
                if self.power_limitation is not None:
                    if self.power_limitation <= 0:
                        raise ValueError("power_limitation must be a positive number (> 0)")
                    if self.power_limitation > MAX_POWER_LIMIT_KW:
                        msg = (
                            f"power_limitation {self.power_limitation} kW "
                            f"exceeds sanity limit of {MAX_POWER_LIMIT_KW} kW"
                        )
                        raise ValueError(msg)

            case OperationMode.HOLD | OperationMode.SELF_CONSUMPTION:
                self._validate_duration()
                if self.power_limitation is not None:
                    raise ValueError(f"power_limitation is not supported for mode {self.mode.name}")
        return self

    def _validate_duration(self) -> None:
        """Shared helper to validate mandatory duration."""
        if self.duration is None:
            raise ValueError(f"duration is required for mode {self.mode.name}")
        if not (1 <= self.duration <= MAX_DURATION_MINS):
            raise ValueError(f"duration must be between 1 and {MAX_DURATION_MINS} minutes")
