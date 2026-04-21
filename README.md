# sig-cloud-control

A Python library and CLI for controlling Sigenergy (Sigen Cloud) solar and battery systems.

> [!CAUTION]
> **Non-Affiliation & Health Warning**
> - **Not Official:** This project is not affiliated with, authorized by, or endorsed by Sigenergy Technology Co., Ltd. Use of this tool is at your own risk.
> - **Warranty Warning:** Using this tool may violate your Sigenergy Terms of Service and could potentially void your hardware warranty. The author is not responsible for any loss of warranty or damage to equipment.
> - **Reverse Engineering:** This tool was developed for the purpose of interoperability between Sigenergy batteries and third-party automation systems.

## Operations

- `charge`: Force charge the battery from the grid.
- `discharge`: Force discharge the battery.
- `hold`: Hold the battery at its current state of charge.
- `self-consumption`: Revert to standard self-consumption mode.
- `cancel`: Stop any active manual control.

## Installation

### From PyPI (Recommended)

```bash
pip install sig-cloud-control
# or using uv
uv tool install sig-cloud-control
```

### From Source (Development)

This project uses `uv` for dependency management.

```bash
# Clone the repository
git clone https://github.com/lawther/sig-cloud-control.git
cd sig-cloud-control

# Install dependencies
uv sync
```

## Configuration

The CLI and library can be configured via a `config.toml` file or environment variables.

### Environment Variables

Environment variables take precedence over the configuration file. This is the recommended way to configure the tool in Docker or headless environments:

- `SIGEN_USERNAME`: Your Sigen Cloud email address.
- `SIGEN_PASSWORD`: Your plaintext password.
- `SIGEN_PASSWORD_ENCODED`: Your encoded password (if you don't want to use plaintext).
- `SIGEN_STATION_ID`: Your Station ID (optional).

### Configuration File

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

Run the CLI using `sig-cloud-control`:

```bash
# Setup credentials interactively (safest way to encrypt password)
sig-cloud-control setup

# Self-consumption for 30 minutes
sig-cloud-control self-consumption 30

# Charge battery for 60 minutes at 2.5kW
sig-cloud-control charge 60 --power 2.5

# Cancel any active manual control
sig-cloud-control cancel
```

## API Usage

You can also use `sig-cloud-control` as a library in your own asynchronous Python applications. The public API is exposed at the root level:

```python
import asyncio
from sig_cloud_control import SigCloudClient, Config

async def main():
    # Initialize config (credentials will be encrypted and stored)
    config = Config(
        username="user@example.com",
        password="my_secret_password"
    )

    # cache_path=None disables the local token cache file
    client = SigCloudClient(config, cache_path=None)
    try:
        # Login
        await client.login()

        # Force charge for 60 minutes at 5.0kW
        await client.charge_battery(duration_min=60, power_kw=5.0)

        print("Charge command issued successfully.")

    finally:
        await client.aclose()

if __name__ == "__main__":
    asyncio.run(main())
```

```

## Development

This project uses `just` to manage development tasks. The `Justfile` is the Single Source Of Truth (SSOT) for all pre-commit checks and development workflows. No additional linting or testing logic should be added anywhere else (e.g. CI configs).

### Help

```bash
just
```

### Running Pre-commit Checks (Lint + Test)

```bash
just precommit
```

### Running Tests

```bash
just test
```

### Linting and Formatting

```bash
just lint
```

## License

Apache 2.0
