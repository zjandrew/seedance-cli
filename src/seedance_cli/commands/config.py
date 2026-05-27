# src/seedance_cli/commands/config.py
from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from seedance_cli.__main__ import emit
from seedance_cli.core.config import (
    DEFAULT_ENDPOINT,
    Profile,
    load,
    mask_api_key,
    save,
)
from seedance_cli.framework.envelope import Success
from seedance_cli.framework.errors import CliError

VALID_SET_KEYS = {"api_key", "endpoint", "default_model"}


@click.group(name="config")
def config() -> None:
    """Manage profiles in ~/.seedance-cli/config.json."""


def _profile_dict(name: str, p: Profile) -> dict[str, Any]:
    return {
        "name": name,
        "api_key": mask_api_key(p.api_key),
        "endpoint": p.endpoint,
        "default_model": p.default_model,
    }


def _config_path() -> Path:
    # Lazy import so tmp_config fixture's monkeypatch on DEFAULT_CONFIG_PATH wins.
    from seedance_cli.core.config import DEFAULT_CONFIG_PATH

    return DEFAULT_CONFIG_PATH


@config.command("list")
@click.pass_context
def config_list(ctx: click.Context) -> None:
    cfg = load(_config_path())
    emit(ctx, Success(data={"active": cfg.active, "profiles": list(cfg.profiles.keys())}))


@config.command("show")
@click.argument("name", required=False)
@click.pass_context
def config_show(ctx: click.Context, name: str | None) -> None:
    cfg = load(_config_path())
    target = name or cfg.active
    if target not in cfg.profiles:
        raise CliError("INVALID_INPUT", f"unknown profile {target!r}")
    emit(ctx, Success(data=_profile_dict(target, cfg.profiles[target])))


@config.command("use")
@click.argument("name")
@click.pass_context
def config_use(ctx: click.Context, name: str) -> None:
    path = _config_path()
    cfg = load(path)
    if name not in cfg.profiles:
        raise CliError("INVALID_INPUT", f"unknown profile {name!r}")
    cfg.active = name
    save(cfg, path)
    emit(ctx, Success(data={"active": name}))


@config.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_context
def config_set(ctx: click.Context, key: str, value: str) -> None:
    if key not in VALID_SET_KEYS:
        raise CliError(
            "INVALID_INPUT",
            f"unknown key {key!r}; valid: {sorted(VALID_SET_KEYS)}",
        )
    path = _config_path()
    cfg = load(path)
    p = cfg.profiles[cfg.active]
    setattr(p, key, value)
    save(cfg, path)
    emit(ctx, Success(data=_profile_dict(cfg.active, p)))


@config.command("unset")
@click.argument("key")
@click.pass_context
def config_unset(ctx: click.Context, key: str) -> None:
    if key not in VALID_SET_KEYS:
        raise CliError("INVALID_INPUT", f"unknown key {key!r}")
    path = _config_path()
    cfg = load(path)
    p = cfg.profiles[cfg.active]
    setattr(p, key, None if key != "endpoint" else DEFAULT_ENDPOINT)
    save(cfg, path)
    emit(ctx, Success(data=_profile_dict(cfg.active, p)))


@config.command("add")
@click.argument("name")
@click.option("--yes", is_flag=True, default=False)
@click.pass_context
def config_add(ctx: click.Context, name: str, yes: bool) -> None:
    path = _config_path()
    cfg = load(path)
    if name in cfg.profiles and not yes:
        raise CliError(
            "INVALID_INPUT",
            f"profile {name!r} already exists; pass --yes to overwrite",
        )
    api_key = click.prompt("API key", hide_input=True, default="", show_default=False)
    endpoint = click.prompt("Endpoint", default=DEFAULT_ENDPOINT, show_default=True)
    model = click.prompt("Default model", default="", show_default=False)
    cfg.profiles[name] = Profile(
        api_key=api_key or None,
        endpoint=endpoint,
        default_model=model or None,
    )
    save(cfg, path)
    emit(ctx, Success(data=_profile_dict(name, cfg.profiles[name])))


@config.command("init")
@click.option("--yes", is_flag=True, default=False)
@click.pass_context
def config_init(ctx: click.Context, yes: bool) -> None:
    path = _config_path()
    cfg = load(path)
    existing = cfg.profiles.get("default")
    if existing is not None and existing.api_key and not yes:
        raise CliError(
            "INVALID_INPUT",
            "default profile already has api_key; pass --yes to overwrite",
        )
    api_key = click.prompt("API key", hide_input=True)
    endpoint = click.prompt("Endpoint", default=DEFAULT_ENDPOINT, show_default=True)
    model = click.prompt("Default model", default="", show_default=False)
    cfg.profiles["default"] = Profile(
        api_key=api_key,
        endpoint=endpoint,
        default_model=model or None,
    )
    cfg.active = "default"
    save(cfg, path)
    emit(ctx, Success(data=_profile_dict("default", cfg.profiles["default"])))
