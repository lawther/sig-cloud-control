import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from sig_cloud_control.cli_app import _DEFAULT_CONFIG_PATH, ConfigSources, SigenEnvVar, app
from sig_cloud_control.models import Config, Region

runner = CliRunner()

ENCODED_PASSWORD = "YWFhYWFhYWFhYWFhYWFhYQ=="
FAKE_CONFIG_PATH = Path("/home/user/.config/sig-cloud-control/config.toml")
EXPECTED_NOT_FOUND_COUNT = 2  # both local and default paths are reported as not found


def _make_config(
    *,
    username: str = "user@example.com",
    password: str | None = None,
    password_encoded: str | None = ENCODED_PASSWORD,
    station_id: int | None = None,
    region: Region = Region.AUS,
) -> Config:
    # Use model_construct to bypass env var loading and field validation entirely.
    return Config.model_construct(
        username=username,
        password=password,
        password_encoded=password_encoded,
        station_id=station_id,
        region=region,
    )


def _console_output(mock_console: MagicMock) -> str:
    """Concatenate all text passed to console.print into one searchable string."""
    return " ".join(str(call.args[0]) for call in mock_console.print.call_args_list if call.args)


# ---------------------------------------------------------------------------
# No configuration found
# ---------------------------------------------------------------------------


def test_show_config_no_config_exits_with_error() -> None:
    # Smoke test: exits 1 when nothing is configured.
    with (
        patch("sig_cloud_control.cli_app._try_load_config", return_value=None),
        patch("pathlib.Path.exists", return_value=False),
        patch.dict(os.environ, {}, clear=True),
        patch("sig_cloud_control.cli_app.console"),
    ):
        result = runner.invoke(app, ["show-config"])

    assert result.exit_code == 1


def test_show_config_no_env_vars_lists_all_sigen_var_names() -> None:
    # When no SIGEN_* env vars are set, all of them are listed so the user
    # knows exactly what to set.
    with (
        patch("sig_cloud_control.cli_app._try_load_config", return_value=None),
        patch("pathlib.Path.exists", return_value=False),
        patch.dict(os.environ, {}, clear=True),
        patch("sig_cloud_control.cli_app.console") as mock_console,
    ):
        runner.invoke(app, ["show-config"])

    output = _console_output(mock_console)
    for var in SigenEnvVar:
        assert str(var) in output, f"Expected {var} in output"
    assert "none set" in output


def test_show_config_partial_env_vars_shows_which_are_set() -> None:
    # If some SIGEN_* vars are present but the config is still incomplete,
    # show which ones were found so the user knows what is missing.
    with (
        patch("sig_cloud_control.cli_app._try_load_config", return_value=None),
        patch("pathlib.Path.exists", return_value=False),
        patch.dict(os.environ, {"SIGEN_USERNAME": "user@example.com"}, clear=True),
        patch("sig_cloud_control.cli_app.console") as mock_console,
    ):
        runner.invoke(app, ["show-config"])

    output = _console_output(mock_console)
    assert "SIGEN_USERNAME" in output
    assert "but insufficient" in output


def test_show_config_no_config_shows_both_file_paths() -> None:
    # Both the local ./config.toml and the platform-default path are shown
    # so the user knows all the places that were checked.
    with (
        patch("sig_cloud_control.cli_app._try_load_config", return_value=None),
        patch("pathlib.Path.exists", return_value=False),
        patch.dict(os.environ, {}, clear=True),
        patch("sig_cloud_control.cli_app.console") as mock_console,
    ):
        runner.invoke(app, ["show-config"])

    output = _console_output(mock_console)
    assert "./config.toml" in output
    assert str(_DEFAULT_CONFIG_PATH) in output
    assert output.count("not found") == EXPECTED_NOT_FOUND_COUNT


def test_show_config_local_file_present_shows_found() -> None:
    # If ./config.toml exists but is still not loadable (e.g. bad content),
    # its status should read "found" rather than "not found".
    def _exists(self: Path) -> bool:
        return str(self) == "config.toml"

    with (
        patch("sig_cloud_control.cli_app._try_load_config", return_value=None),
        patch.object(Path, "exists", _exists),
        patch.dict(os.environ, {}, clear=True),
        patch("sig_cloud_control.cli_app.console") as mock_console,
    ):
        runner.invoke(app, ["show-config"])

    output = _console_output(mock_console)
    assert "config.toml — found" in output
    assert str(_DEFAULT_CONFIG_PATH) in output
    assert "not found" in output  # default path still not found


# ---------------------------------------------------------------------------
# Configuration found — sources display
# ---------------------------------------------------------------------------


def test_show_config_env_vars_only_marks_file_as_not_used() -> None:
    # When env vars alone satisfy the config, the file section should make
    # clear that no file was consulted.
    sources = ConfigSources(
        env_vars_present=frozenset({SigenEnvVar.USERNAME, SigenEnvVar.PASSWORD, SigenEnvVar.REGION}),
        config_file=None,
        config=_make_config(),
    )
    with (
        patch("sig_cloud_control.cli_app._try_load_config", return_value=sources),
        patch("sig_cloud_control.cli_app.console") as mock_console,
    ):
        result = runner.invoke(app, ["show-config"])

    assert result.exit_code == 0
    output = _console_output(mock_console)
    assert "not used" in output
    assert "SIGEN_USERNAME" in output
    assert "SIGEN_PASSWORD" in output
    assert "SIGEN_REGION" in output


def test_show_config_file_only_shows_path_and_no_env_vars() -> None:
    # When the config comes purely from a file with no env overrides, show
    # the file path and mark env vars as none.
    config_path = FAKE_CONFIG_PATH
    sources = ConfigSources(
        env_vars_present=frozenset(),
        config_file=config_path,
        config=_make_config(),
    )
    with (
        patch("sig_cloud_control.cli_app._try_load_config", return_value=sources),
        patch("sig_cloud_control.cli_app.console") as mock_console,
    ):
        result = runner.invoke(app, ["show-config"])

    assert result.exit_code == 0
    output = _console_output(mock_console)
    assert str(config_path) in output
    assert "(none)" in output


def test_show_config_file_and_env_vars_shows_both() -> None:
    # When env vars override some file values, both the file path and the
    # contributing env vars should be visible.
    config_path = FAKE_CONFIG_PATH
    sources = ConfigSources(
        env_vars_present=frozenset({SigenEnvVar.REGION}),
        config_file=config_path,
        config=_make_config(),
    )
    with (
        patch("sig_cloud_control.cli_app._try_load_config", return_value=sources),
        patch("sig_cloud_control.cli_app.console") as mock_console,
    ):
        result = runner.invoke(app, ["show-config"])

    assert result.exit_code == 0
    output = _console_output(mock_console)
    assert str(config_path) in output
    assert "SIGEN_REGION" in output


# ---------------------------------------------------------------------------
# Configuration found — values display
# ---------------------------------------------------------------------------


def test_show_config_shows_username_and_region() -> None:
    sources = ConfigSources(
        env_vars_present=frozenset(),
        config_file=FAKE_CONFIG_PATH,
        config=_make_config(username="test@example.com", region=Region.EU),
    )
    with (
        patch("sig_cloud_control.cli_app._try_load_config", return_value=sources),
        patch("sig_cloud_control.cli_app.console") as mock_console,
    ):
        runner.invoke(app, ["show-config"])

    output = _console_output(mock_console)
    assert "test@example.com" in output
    assert "eu" in output


def test_show_config_masks_plaintext_password() -> None:
    # The actual password value must never appear in the output.
    sources = ConfigSources(
        env_vars_present=frozenset(),
        config_file=FAKE_CONFIG_PATH,
        config=_make_config(password="supersecret", password_encoded=None),
    )
    with (
        patch("sig_cloud_control.cli_app._try_load_config", return_value=sources),
        patch("sig_cloud_control.cli_app.console") as mock_console,
    ):
        runner.invoke(app, ["show-config"])

    output = _console_output(mock_console)
    assert "supersecret" not in output
    assert "*** (plaintext)" in output


def test_show_config_masks_encoded_password() -> None:
    # The base64 password_encoded value must never appear in the output.
    sources = ConfigSources(
        env_vars_present=frozenset(),
        config_file=FAKE_CONFIG_PATH,
        config=_make_config(password=None, password_encoded=ENCODED_PASSWORD),
    )
    with (
        patch("sig_cloud_control.cli_app._try_load_config", return_value=sources),
        patch("sig_cloud_control.cli_app.console") as mock_console,
    ):
        runner.invoke(app, ["show-config"])

    output = _console_output(mock_console)
    assert ENCODED_PASSWORD not in output
    assert "*** (encoded)" in output


def test_show_config_shows_station_id_when_set() -> None:
    sources = ConfigSources(
        env_vars_present=frozenset(),
        config_file=FAKE_CONFIG_PATH,
        config=_make_config(station_id=12345),
    )
    with (
        patch("sig_cloud_control.cli_app._try_load_config", return_value=sources),
        patch("sig_cloud_control.cli_app.console") as mock_console,
    ):
        runner.invoke(app, ["show-config"])

    output = _console_output(mock_console)
    assert "12345" in output
    assert "auto-detect" not in output


def test_show_config_shows_auto_detect_when_station_id_absent() -> None:
    sources = ConfigSources(
        env_vars_present=frozenset(),
        config_file=FAKE_CONFIG_PATH,
        config=_make_config(station_id=None),
    )
    with (
        patch("sig_cloud_control.cli_app._try_load_config", return_value=sources),
        patch("sig_cloud_control.cli_app.console") as mock_console,
    ):
        runner.invoke(app, ["show-config"])

    output = _console_output(mock_console)
    assert "auto-detect" in output
