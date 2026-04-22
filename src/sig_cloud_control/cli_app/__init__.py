import asyncio
import logging
import os
import sys
import tomllib
from enum import StrEnum
from pathlib import Path
from typing import Annotated, NamedTuple

import tomli_w
import typer
from platformdirs import user_config_path
from pydantic import ValidationError
from rich.console import Console

from sig_cloud_control.client import SigCloudClient, SigCloudError
from sig_cloud_control.models import Config, Region

app = typer.Typer(help="Control a Sigen solar/battery station.")

console = Console()

_DEFAULT_CONFIG_PATH: Path = user_config_path("sig-cloud-control") / "config.toml"


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


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Control a Sigen solar/battery station."""
    if ctx.invoked_subcommand is None:
        typer.secho("Missing command.", fg=typer.colors.RED, err=True)
        typer.echo(ctx.get_help())
        raise typer.Exit(code=1)


def perform_setup(config_path: Path) -> None:
    """Interactively prompt for credentials and save to file."""
    typer.echo(f"Setting up new configuration at '{config_path}'...")
    username = typer.prompt("Sigen Cloud login name (eg. user@example.com)")
    password = typer.prompt("Sigen Cloud Password", hide_input=True)
    _region_labels: dict[Region, str] = {
        Region.AUS: "Australia / New Zealand",
        Region.APAC: "Asia-Pacific",
        Region.EU: "Europe",
        Region.CN: "China",
        Region.US: "United States",
    }
    _regions = list(Region)
    typer.echo("Select your region (check your Sigenergy app Settings->System Settings->About):")
    for i, r in enumerate(_regions, 1):
        typer.echo(f"  {i}. {r.value:<6} {_region_labels[r]}")
    while True:
        _choice = typer.prompt(f"Region [1-{len(_regions)}]", type=int)
        if 1 <= _choice <= len(_regions):
            region = _regions[_choice - 1]
            break
        typer.secho(f"Please enter a number between 1 and {len(_regions)}.", fg=typer.colors.RED)
    station_id_str = typer.prompt("Station ID (optional, press Enter to skip)", default="")

    password_encoded = SigCloudClient.encrypt_password(password)

    station_id = int(station_id_str) if station_id_str.strip().isdigit() else None

    config_data: dict[str, object] = {
        "username": username,
        "password_encoded": password_encoded,
        "region": region.value,
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


@app.command(name="show-config")
def show_config(
    config: ConfigOpt = None,
) -> None:
    """Show the current configuration and where it was loaded from."""
    config_path = _resolve_config_path(config)
    sources = _try_load_config(config_path)

    if sources is None:
        env_vars_present = frozenset(v for v in SigenEnvVar if v in os.environ)
        local_config = Path("config.toml")
        console.print("\n[bold yellow]⚠️  No configuration found.[/bold yellow]")
        console.print("\n[bold]Locations checked:[/bold]")
        if not env_vars_present:
            all_vars = ", ".join(sorted(SigenEnvVar))
            console.print(f"  Environment vars:  {all_vars} — [yellow]none set[/yellow]")
        else:
            set_vars = ", ".join(sorted(env_vars_present))
            console.print(f"  Environment vars:  {set_vars} set, but insufficient")
        local_status = "[yellow]not found[/yellow]" if not local_config.exists() else "found"
        console.print(f"  Local config:      ./config.toml — {local_status}")
        default_status = "[yellow]not found[/yellow]" if not _DEFAULT_CONFIG_PATH.exists() else "found"
        console.print(f"  Default config:    {_DEFAULT_CONFIG_PATH} — {default_status}")
        console.print("\nRun [bold]sig-cloud-control setup[/bold] to create a configuration file.")
        raise typer.Exit(code=1)

    console.print("\n[bold]Sources:[/bold]")
    if sources.config_file is not None:
        console.print(f"  Config file:       {sources.config_file}")
    else:
        console.print("  Config file:       [dim](not used — env vars were sufficient)[/dim]")

    if sources.env_vars_present:
        console.print(f"  Environment vars:  {', '.join(sorted(sources.env_vars_present))}")
    else:
        console.print("  Environment vars:  [dim](none)[/dim]")

    console.print("\n[bold]Configuration:[/bold]")
    console.print(f"  Username:          {sources.config.username}")

    if sources.config.password is not None:
        console.print("  Password:          [dim]*** (plaintext)[/dim]")
    elif sources.config.password_encoded is not None:
        console.print("  Password:          [dim]*** (encoded)[/dim]")

    if sources.config.station_id is not None:
        console.print(f"  Station ID:        {sources.config.station_id}")
    else:
        console.print("  Station ID:        [dim](auto-detect)[/dim]")

    console.print(f"  Region:            {sources.config.region.value}")


if __name__ == "__main__":
    app()
