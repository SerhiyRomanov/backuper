"""Shared configuration loading for the Borg CLI and backup workflows."""


def load_config(config_file):
    import yaml

    with open(config_file, "r") as file:
        return yaml.safe_load(file)


def borg_connection(config):
    return {
        "repository": f"{config['repository_path']}:{config['repository_port']}/./{config['repository_name']}",
        "private_key_path": config["private_key_path"],
        "passphrase": config["repository_passphrase"],
    }
