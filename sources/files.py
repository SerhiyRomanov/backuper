"""Back up files and folders."""


def backup(borg, archive_name, config):
    borg.create(archive_name, config["include"], exclude=config.get("exclude", []))
