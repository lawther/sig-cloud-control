import asyncio
import logging
import tomllib
from typing import Annotated, Optional

import typer
from pydantic import ValidationError

from app.client import SigenClient, SigenError
from app.models import Config

app = typer.Typer(help="Control a Sigen solar/battery station.")


async def execute_action(
    config_path: str,
    action: str,
    duration: int = 0,
    power: Optional[float] = None,
    verbose: bool = False,
) -> None:
    """Internal helper to run the async client logic."""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        with open(config_path, "rb") as f:
            config_data = tomllib.load(f)
        config = Config.model_validate(config_data)
    except FileNotFoundError:
        typer.secho(
            f"Error: Config file not found at '{config_path}'",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)
    except ValidationError as e:
        typer.secho(
            f"Error: Invalid configuration format in '{config_path}':\n{e}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

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
        raise typer.Exit(code=1)
    finally:
        await client.aclose()


@app.command()
def charge(
    duration: Annotated[
        int, typer.Argument(help="Duration in minutes (1-1440)", min=1, max=1440)
    ],
    power: Annotated[
        Optional[float], typer.Option(help="Power limitation in kW")
    ] = None,
    config: Annotated[
        str, typer.Option(help="Path to the TOML configuration file")
    ] = "config.toml",
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Enable verbose logging")
    ] = False,
):
    """Charge battery for a specified duration."""
    asyncio.run(execute_action(config, "charge", duration, power, verbose))


@app.command()
def discharge(
    duration: Annotated[
        int, typer.Argument(help="Duration in minutes (1-1440)", min=1, max=1440)
    ],
    power: Annotated[
        Optional[float], typer.Option(help="Power limitation in kW")
    ] = None,
    config: Annotated[
        str, typer.Option(help="Path to the TOML configuration file")
    ] = "config.toml",
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Enable verbose logging")
    ] = False,
):
    """Discharge battery for a specified duration."""
    asyncio.run(execute_action(config, "discharge", duration, power, verbose))


@app.command()
def hold(
    duration: Annotated[
        int, typer.Argument(help="Duration in minutes (1-1440)", min=1, max=1440)
    ],
    power: Annotated[
        Optional[float], typer.Option(help="Power limitation in kW")
    ] = None,
    config: Annotated[
        str, typer.Option(help="Path to the TOML configuration file")
    ] = "config.toml",
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Enable verbose logging")
    ] = False,
):
    """Hold battery for a specified duration."""
    asyncio.run(execute_action(config, "hold", duration, power, verbose))


@app.command(name="self-consumption")
def self_consumption(
    duration: Annotated[
        int, typer.Argument(help="Duration in minutes (1-1440)", min=1, max=1440)
    ],
    power: Annotated[
        Optional[float], typer.Option(help="Power limitation in kW")
    ] = None,
    config: Annotated[
        str, typer.Option(help="Path to the TOML configuration file")
    ] = "config.toml",
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Enable verbose logging")
    ] = False,
):
    """Enable self-consumption mode for a specified duration."""
    asyncio.run(execute_action(config, "self-consumption", duration, power, verbose))


@app.command()
def cancel(
    config: Annotated[
        str, typer.Option(help="Path to the TOML configuration file")
    ] = "config.toml",
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Enable verbose logging")
    ] = False,
):
    """Cancel any active manual control."""
    asyncio.run(execute_action(config, "cancel", verbose=verbose))


if __name__ == "__main__":
    app()
