# tests/integration/test_root.py
from click.testing import CliRunner

from seedance_cli.__main__ import root


def test_root_version():
    res = CliRunner().invoke(root, ["--version"])
    assert res.exit_code == 0
    assert "seedance-cli" in res.output


def test_root_help():
    res = CliRunner().invoke(root, ["--help"])
    assert res.exit_code == 0
    assert "generate" in res.output
    assert "task" in res.output
    assert "config" in res.output


def test_unknown_command_exits_nonzero():
    res = CliRunner().invoke(root, ["nope"])
    assert res.exit_code != 0
