import asyncio
import logging
import tomllib
from pathlib import Path
from typing import Annotated

import typer
from pydantic import ValidationError

from sig_control.client import SigenClient, SigenError
from sig_control.models import Config

app = typer.Typer(help="Control a Sigen solar/battery station.")


def perform_setup(config_path: str) -> Config:
    """Interactively prompt for credentials and save to file."""
    typer.echo(f"Setting up new configuration at '{config_path}'...")
    username = typer.prompt("Sigen Cloud Email")
    password = typer.prompt("Sigen Cloud Password", hide_input=True)

    # Encrypt the password
    password_encoded = SigenClient.encrypt_password(password)

    config_content = f'username = "{username}"\n'
    config_content += f'password_encoded = "{password_encoded}"\n'

    with open(config_path, "w") as f:
        f.write(config_content)

    typer.secho(f"Configuration saved to {config_path}", fg=typer.colors.GREEN)
    typer.echo("Note: Your password has been encrypted for storage.")

    return Config(username=username, password_encoded=password_encoded)


def load_config(config_path: str) -> Config:
    """Load configuration from file, or perform setup if missing."""
    path = Path(config_path)
    if not path.exists():
        typer.secho(f"Config file not found at '{config_path}'", fg=typer.colors.YELLOW)
        return perform_setup(config_path)

    try:
        with open(config_path, "rb") as f:
            config_data = tomllib.load(f)
        return Config.model_validate(config_data)
    except ValidationError as e:
        typer.secho(
            f"Error: Invalid configuration format in '{config_path}':\n{e}",
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
    )

    client = SigenClient(config)
    try:
        await client.login()

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

        typer.secho("Action completed successfully.", fg=typer.colors.GREEN)

    except SigenError as e:
        typer.secho(f"Sigen API Error: {e}", fg=typer.colors.RED, err=True)
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
            f"Warning: Configuration file '{config}' already exists and will be overwritten.",
            fg=typer.colors.YELLOW,
        )

    perform_setup(config)


if __name__ == "__main__":
    app()
