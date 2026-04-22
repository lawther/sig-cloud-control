class SigCloudError(Exception):
    """Base exception for SigCloudClient."""


class AuthenticationError(SigCloudError):
    """Raised when login fails (bad credentials or token error)."""


class StationError(SigCloudError):
    """Raised when the station ID cannot be resolved or is unknown."""


class APIError(SigCloudError):
    """Raised when the Sigen API returns an unexpected or unparseable response."""
