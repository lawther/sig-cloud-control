import asyncio
import logging
import sys

import typer
from rich.console import Console

from sig_cloud_control.client import SigCloudClient, SigCloudError
from sig_cloud_control.models import Config

from .config import _resolve_config_path, load_config

console = Console()


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
