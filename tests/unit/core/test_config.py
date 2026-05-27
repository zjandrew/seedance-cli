# tests/unit/core/test_config.py
import stat
from pathlib import Path

import pytest

from seedance_cli.core.config import (
    DEFAULT_ENDPOINT,
    Config,
    Profile,
    load,
    mask_api_key,
    resolve_profile,
    save,
)
from seedance_cli.framework.errors import CliError


def test_load_returns_empty_when_no_file(tmp_path: Path):
    cfg = load(tmp_path / "missing.json")
    assert cfg.version == 1
    assert cfg.active == "default"
    assert "default" in cfg.profiles
    assert cfg.profiles["default"].api_key is None
    assert cfg.profiles["default"].endpoint == DEFAULT_ENDPOINT


def test_save_then_load_roundtrip(tmp_path: Path):
    cfg = Config(
        active="prod",
        profiles={"prod": Profile(api_key="sk-1234567890", default_model="2.0")},
    )
    path = tmp_path / "config.json"
    save(cfg, path)
    loaded = load(path)
    assert loaded.active == "prod"
    assert loaded.profiles["prod"].api_key == "sk-1234567890"
    assert loaded.profiles["prod"].default_model == "2.0"


def test_save_chmods_to_600(tmp_path: Path):
    path = tmp_path / "config.json"
    save(Config(profiles={"default": Profile(api_key="k")}), path)
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600


def test_save_creates_parent_dirs(tmp_path: Path):
    path = tmp_path / "nested" / "deep" / "config.json"
    save(Config(profiles={"default": Profile()}), path)
    assert path.exists()


def test_mask_api_key():
    assert mask_api_key("sk-abcdefghij1234") == "sk-***1234"
    assert mask_api_key("short") == "***rt"
    assert mask_api_key("") == ""
    assert mask_api_key(None) == ""


def test_resolve_profile_flag_wins():
    cfg = Config(active="b", profiles={"a": Profile(), "b": Profile(), "c": Profile()})
    name = resolve_profile(cli="a", env={"SEEDANCE_PROFILE": "c"}, config=cfg)
    assert name == "a"


def test_resolve_profile_env_beats_active():
    cfg = Config(active="b", profiles={"b": Profile(), "c": Profile()})
    name = resolve_profile(cli=None, env={"SEEDANCE_PROFILE": "c"}, config=cfg)
    assert name == "c"


def test_resolve_profile_falls_back_to_active():
    cfg = Config(active="b", profiles={"a": Profile(), "b": Profile()})
    name = resolve_profile(cli=None, env={}, config=cfg)
    assert name == "b"


def test_resolve_profile_unknown_name_raises():
    cfg = Config(active="default", profiles={"default": Profile()})
    with pytest.raises(CliError) as ei:
        resolve_profile(cli="nope", env={}, config=cfg)
    assert ei.value.code == "INVALID_INPUT"


def test_load_corrupt_json_raises_io_error(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text("{not json")
    with pytest.raises(CliError) as ei:
        load(path)
    assert ei.value.code == "IO_ERROR"
