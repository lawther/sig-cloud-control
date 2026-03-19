import asyncio
import logging
import tomllib
from pathlib import Path
from typing import Annotated

import tomli_w
import typer
from pydantic import ValidationError
from rich.console import Console

from sig_cloud_control.client import SigCloudClient, SigCloudError
from sig_cloud_control.models import Config

app = typer.Typer(help="Control a Sigen solar/battery station.")

LOG_FILE = "sig-cloud-control.log"
console = Console()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Control a Sigen solar/battery station."""
    if ctx.invoked_subcommand is None:
        typer.secho("Missing command.", fg=typer.colors.RED, err=True)
        typer.echo(ctx.get_help())
        raise typer.Exit(code=1)


def perform_setup(config_path: str) -> Config:
    """Interactively prompt for credentials and save to file."""
    typer.echo(f"Setting up new configuration at '{config_path}'...")
    username = typer.prompt("Sigen Cloud login name (eg. user@example.com)")
    password = typer.prompt("Sigen Cloud Password", hide_input=True)
    station_id_str = typer.prompt("Station ID (optional, press Enter to skip)", default="")

    # Encrypt the password
    password_encoded = SigCloudClient.encrypt_password(password)

    station_id = int(station_id_str) if station_id_str.strip().isdigit() else None

    # Prepare data for TOML
    config_data = {
        "username": username,
        "password_encoded": password_encoded,
    }
    if station_id:
        config_data["station_id"] = station_id

    with open(config_path, "wb") as f:
        tomli_w.dump(config_data, f)

    typer.secho("✔︎  ", fg=typer.colors.GREEN, bold=True, nl=False)
    typer.secho(f"Success! Configuration saved to {config_path}", fg=typer.colors.GREEN)
    typer.echo("Note: Your password has been encrypted for storage.")

    return Config(username=username, password_encoded=password_encoded, station_id=station_id)


def load_config(config_path: str) -> Config:
    """Load configuration from file, or perform setup if missing."""
    typer.echo("Loading configuration...")
    path = Path(config_path)
    if not path.exists():
        typer.secho(f"⚠️  Config file not found at '{config_path}'", fg=typer.colors.YELLOW)
        return perform_setup(config_path)

    try:
        with open(config_path, "rb") as f:
            config_data = tomllib.load(f)
        return Config.model_validate(config_data)
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
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        filename=LOG_FILE,
        filemode="a",
    )

    client = SigCloudClient(config)
    try:
        typer.echo("Logging in to Sigen Cloud...")
        await client.login()

        with console.status(f"Executing '{action}' action...", spinner="dots"):
            if action == "charge":
                await client.charge_battery(duration, power)
            elif action == "discharge":
                await client.discharge_battery(duration, power)
            elif action == "hold":
                await client.hold_battery(duration, power)
            elif action == "self-consumption":
                await client.self_consumption(duration, power)
            elif action == "cancel":
                await client.cancel_self_control()

        console.print(f"[bold green]✔︎  [/bold green]Executing '{action}' action... [bold green]Done.[/bold green]")

    except SigCloudError as e:
        typer.secho(f"❌ Sigen API Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from e
    finally:
        await client.aclose()


@app.command()
def charge(
    duration: Annotated[int, typer.Argument(help="Duration in minutes (1-1440)", min=1, max=1440)],
    power: Annotated[float | None, typer.Option(help="Power limitation in kW")] = None,
    config: Annotated[str, typer.Option(help="Path to the TOML configuration file")] = "config.toml",
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose logging")] = False,
) -> None:
    """Charge battery for a specified duration."""
    conf = load_config(config)
    asyncio.run(execute_action(conf, "charge", duration, power, verbose))


@app.command()
def discharge(
    duration: Annotated[int, typer.Argument(help="Duration in minutes (1-1440)", min=1, max=1440)],
    power: Annotated[float | None, typer.Option(help="Power limitation in kW")] = None,
    config: Annotated[str, typer.Option(help="Path to the TOML configuration file")] = "config.toml",
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose logging")] = False,
) -> None:
    """Discharge battery for a specified duration."""
    conf = load_config(config)
    asyncio.run(execute_action(conf, "discharge", duration, power, verbose))


@app.command()
def hold(
    duration: Annotated[int, typer.Argument(help="Duration in minutes (1-1440)", min=1, max=1440)],
    power: Annotated[float | None, typer.Option(help="Power limitation in kW")] = None,
    config: Annotated[str, typer.Option(help="Path to the TOML configuration file")] = "config.toml",
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose logging")] = False,
) -> None:
    """Hold battery for a specified duration."""
    conf = load_config(config)
    asyncio.run(execute_action(conf, "hold", duration, power, verbose))


@app.command(name="self-consumption")
def self_consumption(
    duration: Annotated[int, typer.Argument(help="Duration in minutes (1-1440)", min=1, max=1440)],
    power: Annotated[float | None, typer.Option(help="Power limitation in kW")] = None,
    config: Annotated[str, typer.Option(help="Path to the TOML configuration file")] = "config.toml",
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose logging")] = False,
) -> None:
    """Enable self-consumption mode for a specified duration."""
    conf = load_config(config)
    asyncio.run(execute_action(conf, "self-consumption", duration, power, verbose))


@app.command()
def cancel(
    config: Annotated[str, typer.Option(help="Path to the TOML configuration file")] = "config.toml",
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose logging")] = False,
) -> None:
    """Cancel any active manual control."""
    conf = load_config(config)
    asyncio.run(execute_action(conf, "cancel", verbose=verbose))


@app.command()
def setup(
    config: Annotated[str, typer.Option(help="Path to the TOML configuration file to create")] = "config.toml",
) -> None:
    """Interactively setup credentials and save to config file."""
    path = Path(config)
    if path.exists():
        typer.secho(
            f"⚠️  Warning: Configuration file '{config}' already exists and will be overwritten.",
            fg=typer.colors.YELLOW,
        )

    perform_setup(config)


if __name__ == "__main__":
    app()
