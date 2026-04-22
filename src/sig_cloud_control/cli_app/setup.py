import os
from pathlib import Path

import tomli_w
import typer

from sig_cloud_control._encryption import encrypt_password
from sig_cloud_control.models import Region


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

    password_encoded = encrypt_password(password)

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
