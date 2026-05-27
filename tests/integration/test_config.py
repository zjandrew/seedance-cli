# tests/integration/test_config.py
import json
from pathlib import Path

from click.testing import CliRunner

from seedance_cli.__main__ import root


def _cli() -> CliRunner:
    return CliRunner()


def test_config_list_empty(tmp_config: Path):
    res = _cli().invoke(root, ["config", "list"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)
    assert data == {"ok": True, "data": {"active": "default", "profiles": ["default"]}}


def test_config_set_and_show(tmp_config: Path):
    r1 = _cli().invoke(root, ["config", "set", "api_key", "sk-abcdef1234567890"])
    assert r1.exit_code == 0
    r2 = _cli().invoke(root, ["config", "show"])
    assert r2.exit_code == 0
    data = json.loads(r2.output)["data"]
    assert data["api_key"] == "sk-***7890"
    assert data["endpoint"].startswith("https://ark.cn-beijing.volces.com")


def test_config_add_and_use(tmp_config: Path):
    # Provide TTY-prompt answers: api_key, endpoint (default), default_model (empty)
    r1 = _cli().invoke(root, ["config", "add", "prod", "--yes"], input="sk-prodkey\n\n\n")
    assert r1.exit_code == 0, r1.output
    r2 = _cli().invoke(root, ["config", "use", "prod"])
    assert r2.exit_code == 0
    r3 = _cli().invoke(root, ["config", "list"])
    listing = json.loads(r3.output)["data"]
    assert listing["active"] == "prod"
    assert "prod" in listing["profiles"]


def test_config_set_unknown_key_rejected(tmp_config: Path):
    res = _cli().invoke(root, ["config", "set", "bogus", "x"])
    assert res.exit_code == 2  # INVALID_INPUT → exit 2
    parsed = json.loads(res.output)
    assert parsed["error"]["code"] == "INVALID_INPUT"


def test_config_unset_clears_field(tmp_config: Path):
    _cli().invoke(root, ["config", "set", "default_model", "2.0"])
    res = _cli().invoke(root, ["config", "unset", "default_model"])
    assert res.exit_code == 0
    shown = json.loads(_cli().invoke(root, ["config", "show"]).output)["data"]
    assert shown["default_model"] is None
