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
3. Enter your password (plaintext) OR your **encoded** password. 

```toml
username = "example@example.com"
password = "your_plaintext_password"

# OR use the encoded password from the browser:
# password_encoded = "..."

# station_id is optional and will be fetched automatically if omitted
# station_id = 12345
```

## CLI Usage

Run the CLI using `uv run main.py`:

```bash
# Setup credentials interactively (safest way to encrypt password)
uv run main.py setup

# Self-consumption for 30 minutes
uv run main.py self-consumption 30

# Charge battery for 60 minutes at 2.5kW
uv run main.py charge 60 --power 2.5

# Cancel any active manual control
uv run main.py cancel
```

## API Usage

You can also use `sig-control` as a library in your own asynchronous Python applications:

```python
import asyncio
from app.client import SigenClient
from app.models import Config

async def main():
    # Initialize config (password will be encrypted automatically)
    config = Config(
        username="user@example.com",
        password="my_secret_password"
    )

    client = SigenClient(config)
    try:
        # Login (uses cache if available)
        await client.login()
        
        # Force charge for 60 minutes at 5.0kW
        await client.charge_battery(duration_min=60, power_kw=5.0)
        
        print("Charge command issued successfully.")
        
    finally:
        await client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
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
