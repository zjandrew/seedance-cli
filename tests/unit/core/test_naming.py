# tests/unit/core/test_naming.py
from pathlib import Path

import pytest

from seedance_cli.core.naming import resolve_out_path
from seedance_cli.framework.errors import CliError


def test_no_out_lands_in_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    p = resolve_out_path(out=None, task_id="cgt-abcdef123", created_at=1700000000, ext="mp4")
    assert p.parent == tmp_path
    assert p.name.endswith(".mp4")
    assert "1700000000" in p.name
    assert "abcdef" in p.name  # short id segment


def test_explicit_file_path(tmp_path: Path):
    target = tmp_path / "my.mp4"
    p = resolve_out_path(out=str(target), task_id="cgt-1", created_at=0, ext="mp4")
    assert p == target


def test_explicit_file_missing_parent_raises(tmp_path: Path):
    target = tmp_path / "missing-subdir" / "my.mp4"
    with pytest.raises(CliError) as ei:
        resolve_out_path(out=str(target), task_id="cgt-1", created_at=0, ext="mp4")
    assert ei.value.code == "IO_ERROR"


def test_directory_with_trailing_slash_auto_creates(tmp_path: Path):
    d = tmp_path / "new" / "sub"
    p = resolve_out_path(out=str(d) + "/", task_id="cgt-xyz789", created_at=1700000000, ext="mp4")
    assert p.parent == d
    assert d.is_dir()
    assert p.name.endswith(".mp4")


def test_extension_swap_for_last_frame(tmp_path: Path):
    p = resolve_out_path(out=None, task_id="cgt-1", created_at=0, ext="png")
    assert p.suffix == ".png"


def test_directory_with_tilde_expands_to_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Point HOME at tmp_path so the test doesn't litter the real home dir.
    monkeypatch.setenv("HOME", str(tmp_path))
    p = resolve_out_path(out="~/clips/", task_id="cgt-1", created_at=0, ext="mp4")
    assert p.parent == tmp_path / "clips"
    assert (tmp_path / "clips").is_dir()


def test_explicit_file_with_tilde_expands_to_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Already worked before the fix; lock the behavior to prevent regression.
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "subdir").mkdir()
    p = resolve_out_path(out="~/subdir/result.mp4", task_id="cgt-1", created_at=0, ext="mp4")
    assert p == tmp_path / "subdir" / "result.mp4"
