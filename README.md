# sig-control

A Python library and CLI for controlling Sigenergy (Sigen Cloud) solar and battery systems.

## Operations

- `charge`: Force charge the battery from the grid.
- `discharge`: Force discharge the battery.
- `hold`: Hold the battery at its current state of charge.
- `self-consumption`: Revert to standard self-consumption mode.
- `cancel`: Stop any active manual control.

## Installation

This project uses `uv` for dependency management.

```bash
# Clone the repository
git clone <repository-url>
cd sig-control

# Install dependencies
uv sync
```

## Configuration

1. Copy `config.sample.toml` to `config.toml`.
2. Enter your Sigen Cloud email address.
3. Enter your **encoded** password. This can be found by inspecting the network traffic in your browser when logging into the Sigen Cloud dashboard. Look for the `password` field in the payload of the `/auth/oauth/token` request.

```toml
username = "example@example.com"
password_encoded = "..."
# station_id is optional and will be fetched automatically if omitted
```

## CLI Usage

Run the CLI using `uv run main.py`:

```bash
# Self-consumption for 30 minutes
uv run main.py self-consumption 30

# Charge battery for 60 minutes at 2.5kW
uv run main.py charge 60 --power 2.5

# Cancel any active manual control
uv run main.py cancel
```

## Development

### Running Tests

```bash
uv run pytest
```

### Linting and Formatting

```bash
uv run ruff check --fix
uv run ruff format
```

## License

MIT
