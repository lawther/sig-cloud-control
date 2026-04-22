from unittest.mock import AsyncMock, MagicMock, patch

from typer.testing import CliRunner

from sig_cloud_control.cli_app import app

runner = CliRunner()

MOCK_DURATION = 30
MOCK_POWER = 5.0


def test_cli_help_loads() -> None:
    # Smoke test: verifies all CLI dependencies (typer, tomli_w, etc.) are importable
    # and the app initialises without error. Regression for missing cli dependencies.
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0


def test_charge_command() -> None:
    with (
        patch("sig_cloud_control.cli_app.actions.load_config") as mock_load,
        patch("sig_cloud_control.cli_app.actions.execute_action", new_callable=AsyncMock) as mock_execute,
    ):
        mock_load.return_value = MagicMock()

        result = runner.invoke(app, ["charge", str(MOCK_DURATION), "--power", str(MOCK_POWER)])

        assert result.exit_code == 0
        # load_config is called once with whatever path was resolved
        mock_load.assert_called_once()
        mock_execute.assert_called_once()
        # The first arg is the config from mock_load.return_value
        args, _ = mock_execute.call_args
        # execute_action(config, action, duration, power, verbose)
        assert args[1] == "charge"
        assert args[2] == MOCK_DURATION
        assert args[3] == MOCK_POWER
        assert args[4] is False  # verbose default


def test_hold_rejects_power_option() -> None:
    # --power is not a valid option for hold; rate limiting is not supported for this mode
    result = runner.invoke(app, ["hold", "60", "--power", "3.0"])
    assert result.exit_code != 0


def test_self_consumption_rejects_power_option() -> None:
    # --power is not a valid option for self-consumption; rate limiting is not supported for this mode
    result = runner.invoke(app, ["self-consumption", "60", "--power", "3.0"])
    assert result.exit_code != 0
