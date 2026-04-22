from pathlib import Path

from platformdirs import user_config_path

_DEFAULT_CONFIG_PATH: Path = user_config_path("sig-cloud-control") / "config.toml"
