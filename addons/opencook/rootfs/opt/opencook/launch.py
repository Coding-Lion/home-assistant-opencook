"""Translate Supervisor options, prepare persistent storage, then run as uid 10001."""

import json
import os
from pathlib import Path

DATA_DIR = Path("/data/opencook")
OPTION_ENV = {
    "server_name": "OPENCOOK_SERVER_NAME",
    "admin_password": "OPENCOOK_ADMIN_PASSWORD",
    "vision_base_url": "OPENCOOK_VISION_BASE_URL",
    "vision_model": "OPENCOOK_VISION_MODEL",
    "vision_api_key": "OPENCOOK_VISION_API_KEY",
    "backup_keep": "OPENCOOK_BACKUP_KEEP",
}


def build_environment(options: dict, inherited: dict) -> dict:
    """Do not forward empty secrets or log option values."""
    environment = dict(inherited)
    for option, variable in OPTION_ENV.items():
        value = options.get(option)
        if value is not None and value != "":
            environment[variable] = str(value)
        else:
            environment.pop(variable, None)
    environment["OPENCOOK_DATA_DIR"] = str(DATA_DIR)
    environment["OPENCOOK_HOST"] = "0.0.0.0"
    environment["OPENCOOK_PORT"] = "8000"
    environment["HOME"] = str(DATA_DIR)
    return environment


def main() -> None:
    """Supervisor preserves /data across updates and includes it in backups."""
    options = json.loads(Path("/data/options.json").read_text())
    environment = build_environment(options, os.environ)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # Backups or migration from a root-run installation may have different owners.
    os.chown(DATA_DIR, 10001, 10001)
    for parent, directories, files in os.walk(DATA_DIR):
        for name in directories + files:
            path = Path(parent) / name
            if not path.is_symlink():
                os.chown(path, 10001, 10001)
    os.setgroups([])
    os.setgid(10001)
    os.setuid(10001)
    os.chdir(DATA_DIR)
    print("Starting openCook on port 8000; persistent data: /data/opencook", flush=True)
    os.execvpe(
        "uvicorn",
        [
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--log-level",
            options.get("log_level", "info"),
        ],
        environment,
    )


if __name__ == "__main__":
    main()
