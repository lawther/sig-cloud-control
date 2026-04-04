import sys
from unittest.mock import MagicMock

# Mock tomli_w before importing the app because it's missing in the environment
sys.modules["tomli_w"] = MagicMock()

from unittest.mock import patch  # noqa: E402

from typer.testing import CliRunner  # noqa: E402

from sig_cloud_control.cli_app import app  # noqa: E402

runner = CliRunner()

MOCK_DURATION = 30
MOCK_POWER = 5.0


def test_charge_command() -> None:
    with (
        patch("sig_cloud_control.cli_app.load_config") as mock_load,
        patch("sig_cloud_control.cli_app.execute_action") as mock_execute,
    ):
        mock_load.return_value = MagicMock()

        result = runner.invoke(app, ["charge", str(MOCK_DURATION), "--power", str(MOCK_POWER)])

        assert result.exit_code == 0
        mock_load.assert_called_once_with("config.toml")
        mock_execute.assert_called_once()
        # The first arg is the config from mock_load.return_value
        args, _ = mock_execute.call_args
        # execute_action(config, action, duration, power, verbose)
        assert args[1] == "charge"
        assert args[2] == MOCK_DURATION
        assert args[3] == MOCK_POWER
        assert args[4] is False  # verbose default
