import os
import tomllib
from enum import StrEnum
from pathlib import Path
from typing import NamedTuple

import typer
from pydantic import ValidationError

from sig_cloud_control.models import Config, Region

from .constants import _DEFAULT_CONFIG_PATH
from .setup import perform_setup


class SigenEnvVar(StrEnum):
    """Sigen environment variable names.

    Each member name (lowercased) is the corresponding Config field name,
    and each value is the environment variable name.
    """

    USERNAME = "SIGEN_USERNAME"
    PASSWORD = "SIGEN_PASSWORD"  # noqa: S105
    PASSWORD_ENCODED = "SIGEN_PASSWORD_ENCODED"  # noqa: S105
    STATION_ID = "SIGEN_STATION_ID"
    REGION = "SIGEN_REGION"


class ConfigSources(NamedTuple):
    """The resolved configuration and the sources it was loaded from."""

    env_vars_present: frozenset[SigenEnvVar]
    config_file: Path | None
    config: Config


def _resolve_config_path(config_opt: str | None) -> Path:
    """Resolve config path: explicit CLI arg > ./config.toml > platform default."""
    if config_opt is not None:
        return Path(config_opt)
    local = Path("config.toml")
    if local.exists():
        return local
    return _DEFAULT_CONFIG_PATH


def _try_load_config(config_path: Path) -> ConfigSources | None:
    """Attempt to load config from env vars and/or a TOML file.

    Returns None if no valid config could be assembled (without triggering interactive setup).
    Precedence: SIGEN_* environment variables override file values.
    """
    env_vars_present = frozenset(v for v in SigenEnvVar if v in os.environ)

    try:
        config = Config.model_validate({})
        return ConfigSources(env_vars_present=env_vars_present, config_file=None, config=config)
    except ValidationError:
        pass

    if not config_path.exists():
        return None

    try:
        with open(config_path, "rb") as f:
            file_data: dict[str, object] = tomllib.load(f)

        # TOML parses region as a plain string; coerce to Region for strict-mode validation.
        # (env_settings handles this automatically; init_settings does not.)
        if "region" in file_data and isinstance(file_data["region"], str):
            file_data["region"] = Region(file_data["region"])

        # env_settings overrides init_settings per Config.settings_customise_sources.
        config = Config(**file_data)
        return ConfigSources(env_vars_present=env_vars_present, config_file=config_path, config=config)
    except ValidationError as e:
        typer.secho(
            f"❌ Error: Invalid configuration format in '{config_path}':\n{e}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from e


def load_config(config_path: Path) -> Config:
    """Load configuration from environment variables and/or TOML file, prompting for setup if missing."""
    typer.echo("Loading configuration...")
    sources = _try_load_config(config_path)
    if sources is None:
        typer.secho(f"⚠️  Config file not found at '{config_path}'", fg=typer.colors.YELLOW)
        perform_setup(config_path)
        sources = _try_load_config(config_path)
        if sources is None:
            typer.secho("❌ Configuration unavailable after setup.", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
    return sources.config
