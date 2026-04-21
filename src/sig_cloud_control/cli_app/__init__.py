import asyncio
import logging
import os
import sys
import tomllib
from pathlib import Path
from typing import Annotated

import tomli_w
import typer
from platformdirs import user_config_path
from pydantic import ValidationError
from rich.console import Console

from sig_cloud_control.client import SigCloudClient, SigCloudError
from sig_cloud_control.models import Config

app = typer.Typer(help="Control a Sigen solar/battery station.")

console = Console()

_DEFAULT_CONFIG_PATH: Path = user_config_path("sig-cloud-control") / "config.toml"


def _resolve_config_path(config_opt: str | None) -> Path:
    """Resolve config path: explicit CLI arg > ./config.toml > platform default."""
    if config_opt is not None:
        return Path(config_opt)
    local = Path("config.toml")
    if local.exists():
        return local
    return _DEFAULT_CONFIG_PATH


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Control a Sigen solar/battery station."""
    if ctx.invoked_subcommand is None:
        typer.secho("Missing command.", fg=typer.colors.RED, err=True)
        typer.echo(ctx.get_help())
        raise typer.Exit(code=1)


def perform_setup(config_path: Path) -> Config:
    """Interactively prompt for credentials and save to file."""
    typer.echo(f"Setting up new configuration at '{config_path}'...")
    username = typer.prompt("Sigen Cloud login name (eg. user@example.com)")
    password = typer.prompt("Sigen Cloud Password", hide_input=True)
    station_id_str = typer.prompt("Station ID (optional, press Enter to skip)", default="")

    password_encoded = SigCloudClient.encrypt_password(password)

    station_id = int(station_id_str) if station_id_str.strip().isdigit() else None

    config_data: dict[str, object] = {
        "username": username,
        "password_encoded": password_encoded,
    }
    if station_id:
        config_data["station_id"] = station_id

    config_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(config_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        tomli_w.dump(config_data, f)

    typer.secho("✔︎  ", fg=typer.colors.GREEN, bold=True, nl=False)
    typer.secho(f"Success! Configuration saved to {config_path}", fg=typer.colors.GREEN)
    typer.echo("Note: Your password has been encrypted for storage.")

    return Config(username=username, password_encoded=password_encoded, station_id=station_id)


def load_config(config_path: Path) -> Config:
    """Load configuration from environment variables and/or TOML file.

    Precedence:
    1. SIGEN_* Environment Variables
    2. TOML file at config_path
    3. Interactive setup (if both are missing)
    """
    typer.echo("Loading configuration...")

    # Load from environment variables first
    try:
        # Config() automatically loads from os.environ due to BaseSettings inheritance
        # If it returns a valid config, then environment variables have everything we need.
        return Config()
    except ValidationError:
        # Not enough in env vars, we'll try to supplement with the file
        pass

    if not config_path.exists():
        typer.secho(f"⚠️  Config file not found at '{config_path}'", fg=typer.colors.YELLOW)
        return perform_setup(config_path)

    try:
        with open(config_path, "rb") as f:
            file_data = tomllib.load(f)

        # Get what we have from environment variables (even if it's incomplete)
        env_vars: dict[str, object] = {
            "username": os.environ.get("SIGEN_USERNAME"),
            "password": os.environ.get("SIGEN_PASSWORD"),
            "password_encoded": os.environ.get("SIGEN_PASSWORD_ENCODED"),
            "station_id": os.environ.get("SIGEN_STATION_ID"),
        }
        # Filter out None values and convert types
        env_vars = {k: v for k, v in env_vars.items() if v is not None}
        if "station_id" in env_vars and isinstance(env_vars["station_id"], str) and env_vars["station_id"].isdigit():
            env_vars["station_id"] = int(env_vars["station_id"])

        # Merge: Environment Variables OVER file data
        merged_data = {**file_data, **env_vars}
        return Config.model_validate(merged_data)
    except ValidationError as e:
        typer.secho(
            f"❌ Error: Invalid configuration format in '{config_path}':\n{e}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from e


async def execute_action(
    config: Config,
    action: str,
    duration: int = 0,
    power: float | None = None,
    verbose: bool = False,
) -> None:
    """Internal helper to run the async client logic."""
    if verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            stream=sys.stderr,
        )

    async with SigCloudClient(config) as client:
        typer.echo("Logging in to Sigen Cloud...")
        await client.login()

        with console.status(f"Executing '{action}' action...", spinner="dots"):
            if action == "charge":
                await client.charge_battery(duration, power)
            elif action == "discharge":
                await client.discharge_battery(duration, power)
            elif action == "hold":
                await client.hold_battery(duration)
            elif action == "self-consumption":
                await client.self_consumption(duration)
            elif action == "cancel":
                await client.cancel_self_control()

    console.print(f"[bold green]✔︎  [/bold green]Executing '{action}' action... [bold green]Done.[/bold green]")


# Common types for CLI arguments and options to reduce duplication
DurationArg = Annotated[int, typer.Argument(help="Duration in minutes (1-1440)", min=1, max=1440)]
PowerOpt = Annotated[float | None, typer.Option(help="Charge/discharge rate limit for the battery in kW")]
ConfigOpt = Annotated[str | None, typer.Option(help="Path to the TOML configuration file")]
VerboseOpt = Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose logging")]


def _run_command_action(
    action: str,
    duration: int = 0,
    power: float | None = None,
    config: str | None = None,
    verbose: bool = False,
) -> None:
    """Internal helper to load config and run an action."""
    conf = load_config(_resolve_config_path(config))
    try:
        asyncio.run(execute_action(conf, action, duration, power, verbose))
    except SigCloudError as e:
        typer.secho(f"❌ Sigen API Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e


@app.command()
def charge(
    duration: DurationArg,
    power: PowerOpt = None,
    config: ConfigOpt = None,
    verbose: VerboseOpt = False,
) -> None:
    """Charge battery from the grid for a specified duration."""
    _run_command_action("charge", duration, power, config, verbose)


@app.command()
def discharge(
    duration: DurationArg,
    power: PowerOpt = None,
    config: ConfigOpt = None,
    verbose: VerboseOpt = False,
) -> None:
    """Discharge battery for a specified duration."""
    _run_command_action("discharge", duration, power, config, verbose)


@app.command()
def hold(
    duration: DurationArg,
    config: ConfigOpt = None,
    verbose: VerboseOpt = False,
) -> None:
    """Hold battery at its current state of charge for a specified duration."""
    _run_command_action("hold", duration, config=config, verbose=verbose)


@app.command(name="self-consumption")
def self_consumption(
    duration: DurationArg,
    config: ConfigOpt = None,
    verbose: VerboseOpt = False,
) -> None:
    """Enable self-consumption mode for a specified duration."""
    _run_command_action("self-consumption", duration, config=config, verbose=verbose)


@app.command()
def cancel(
    config: ConfigOpt = None,
    verbose: VerboseOpt = False,
) -> None:
    """Return the battery to its configured default mode."""
    _run_command_action(action="cancel", config=config, verbose=verbose)


@app.command()
def setup(
    config: Annotated[str | None, typer.Option(help="Path to the TOML configuration file to create")] = None,
) -> None:
    """Interactively setup credentials and save to config file."""
    config_path = Path(config) if config else _DEFAULT_CONFIG_PATH
    if config_path.exists():
        typer.secho(
            f"⚠️  Warning: Configuration file '{config_path}' already exists and will be overwritten.",
            fg=typer.colors.YELLOW,
        )

    perform_setup(config_path)


if __name__ == "__main__":
    app()
