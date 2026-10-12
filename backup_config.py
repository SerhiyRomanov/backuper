"""Shared configuration loading for the Borg CLI and backup workflows."""


def load_config(config_file):
    try:
        import yaml
    except ImportError as error:
        raise ValueError("PyYAML is required. Install it with: python3 -m pip install PyYAML") from error

    with open(config_file, "r") as file:
        try:
            config = yaml.safe_load(file)
        except yaml.YAMLError as error:
            raise ValueError(f"Invalid YAML configuration: {error}") from error
    if not isinstance(config, dict):
        raise ValueError("The config file must contain a YAML mapping.")
    return config


def borg_connection(config):
    required = (
        "repository_path", "repository_port", "repository_name",
        "private_key_path", "repository_passphrase",
    )
    missing = [key for key in required if not config.get(key)]
    if missing:
        raise ValueError(f"Missing required configuration parameters: {', '.join(missing)}")
    return {
        "repository": f"{config['repository_path']}:{config['repository_port']}/./{config['repository_name']}",
        "private_key_path": config["private_key_path"],
        "passphrase": config["repository_passphrase"],
    }
