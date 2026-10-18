"""Configuration: packaged defaults merged with the user's TOML files."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

APP = "handsfree"


def _xdg(var: str, fallback: str) -> Path:
    value = os.environ.get(var)
    return Path(value) if value else Path.home() / fallback


def config_dir() -> Path:
    return _xdg("XDG_CONFIG_HOME", ".config") / APP


def state_dir() -> Path:
    return _xdg("XDG_STATE_HOME", ".local/state") / APP


def data_dir() -> Path:
    return _xdg("XDG_DATA_HOME", ".local/share") / "omarchy-handsfree"


def runtime_dir() -> Path:
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/{APP}-{os.getuid()}"
    return Path(base) / APP


def socket_path() -> Path:
    return runtime_dir() / "control.sock"


def state_file() -> Path:
    return runtime_dir() / "state.json"


def deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _default(name: str) -> dict[str, Any]:
    return tomllib.loads(resources.files("handsfree.data").joinpath(name).read_text())


def load_settings(directory: Path | None = None) -> dict[str, Any]:
    data = _default("config.toml")
    path = (directory or config_dir()) / "config.toml"
    if path.exists():
        data = deep_merge(data, tomllib.loads(path.read_text()))
    return data


def load_commands(directory: Path | None = None) -> dict[str, Any]:
    """User commands are tried before the defaults; [sites] tables are merged."""
    data = _default("commands.toml")
    path = (directory or config_dir()) / "commands.toml"
    if path.exists():
        user = tomllib.loads(path.read_text())
        user_commands = user.pop("command", [])
        defaults = data.pop("command", [])
        if user.pop("replace_defaults", False):
            defaults = []
        data = deep_merge(data, user)
        data["command"] = user_commands + defaults
    return data


@dataclass
class Config:
    settings: dict[str, Any]
    commands: dict[str, Any]

    @classmethod
    def load(cls, directory: Path | None = None) -> "Config":
        return cls(load_settings(directory), load_commands(directory))

    def section(self, name: str) -> dict[str, Any]:
        return self.settings.get(name, {})
