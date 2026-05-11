from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path


@dataclass(frozen=True)
class GustavCLIConfig:
    base_url: str
    token: str


def default_config_path() -> Path:
    root = (
        os.getenv("GUSTAV_CONFIG_HOME")
        or os.getenv("XDG_CONFIG_HOME")
        or str(Path.home() / ".config")
    )
    return Path(root) / "gustav" / "config.json"


def save_config(config: GustavCLIConfig, path: Path | None = None) -> Path:
    target = path or default_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"base_url": config.base_url.rstrip("/"), "token": config.token}, indent=2)
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.write("\n")
    os.chmod(target, 0o600)
    return target


def load_config(path: Path | None = None) -> GustavCLIConfig:
    target = path or default_config_path()
    data = json.loads(target.read_text(encoding="utf-8"))
    return GustavCLIConfig(base_url=str(data["base_url"]).rstrip("/"), token=str(data["token"]))
