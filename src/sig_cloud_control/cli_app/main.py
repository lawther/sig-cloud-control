import os
from pathlib import Path
from typing import Annotated

import typer

from .actions import _run_command_action, console
from .config import SigenEnvVar, _resolve_config_path, _try_load_config
from .constants import _DEFAULT_CONFIG_PATH
from .setup import perform_setup

app = typer.Typer(help="Control a Sigen solar/battery station.")

# Common types for CLI arguments and options to reduce duplication
DurationArg = Annotated[int, typer.Argument(help="Duration in minutes (1-1440)", min=1, max=1440)]
PowerOpt = Annotated[float | None, typer.Option(help="Charge/discharge rate limit for the battery in kW")]
ConfigOpt = Annotated[str | None, typer.Option(help="Path to the TOML configuration file")]
VerboseOpt = Annotated[bool, typer.Option("--verbose", "-v", help="Enable verbose logging")]


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Control a Sigen solar/battery station."""
    if ctx.invoked_subcommand is None:
        typer.secho("Missing command.", fg=typer.colors.RED, err=True)
        typer.echo(ctx.get_help())
        raise typer.Exit(code=1)


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
