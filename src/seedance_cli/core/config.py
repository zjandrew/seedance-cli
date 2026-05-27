# src/seedance_cli/core/config.py
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, cast

from seedance_cli.framework.errors import CliError

DEFAULT_ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_CONFIG_PATH = Path.home() / ".seedance-cli" / "config.json"


@dataclass
class Profile:
    api_key: str | None = None
    endpoint: str = DEFAULT_ENDPOINT
    default_model: str | None = None


@dataclass
class Config:
    version: int = 1
    active: str = "default"
    profiles: dict[str, Profile] = field(default_factory=lambda: {"default": Profile()})


def load(path: Path = DEFAULT_CONFIG_PATH) -> Config:
    if not path.exists():
        return Config()
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise CliError("IO_ERROR", f"config file is not valid JSON: {path} ({e})") from e
    except OSError as e:
        raise CliError("IO_ERROR", f"cannot read config: {path} ({e})") from e

    if not isinstance(raw, dict):
        raise CliError(
            "IO_ERROR",
            f"config file root must be a JSON object: {path}",
        )

    raw_dict: dict[str, Any] = cast("dict[str, Any]", raw)

    try:
        profiles_raw_obj: Any = raw_dict.get("profiles") or {}
        if not isinstance(profiles_raw_obj, dict):
            raise TypeError(f"'profiles' must be an object, got {type(profiles_raw_obj).__name__}")
        profiles_raw: dict[str, Any] = cast("dict[str, Any]", profiles_raw_obj)
        profiles: dict[str, Profile] = {
            name: Profile(
                api_key=p.get("api_key"),
                endpoint=p.get("endpoint", DEFAULT_ENDPOINT),
                default_model=p.get("default_model"),
            )
            for name, p in profiles_raw.items()
        }  # pyright: ignore[reportUnknownVariableType,reportUnknownMemberType,reportUnknownArgumentType]
    except (TypeError, AttributeError, KeyError) as e:
        raise CliError(
            "IO_ERROR",
            f"config file has malformed structure: {path} ({e})",
        ) from e

    if not profiles:
        profiles = {"default": Profile()}
    return Config(
        version=raw_dict.get("version", 1),
        active=raw_dict.get("active", "default"),
        profiles=profiles,
    )


def save(cfg: Config, path: Path = DEFAULT_CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = {
        "version": cfg.version,
        "active": cfg.active,
        "profiles": {name: asdict(p) for name, p in cfg.profiles.items()},
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(serialized, indent=2, ensure_ascii=False))
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def mask_api_key(key: str | None) -> str:
    if not key:
        return ""
    if len(key) <= 6:
        return "***" + key[-2:]
    return f"{key[:3]}***{key[-4:]}"


def resolve_profile(*, cli: str | None, env: dict[str, str], config: Config) -> str:
    name = cli or env.get("SEEDANCE_PROFILE") or config.active
    if name not in config.profiles:
        raise CliError(
            "INVALID_INPUT",
            f"unknown profile {name!r}",
            details={"available": list(config.profiles.keys())},
        )
    return name
