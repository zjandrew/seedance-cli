# src/seedance_cli/core/naming.py
from __future__ import annotations

import os
from pathlib import Path

from seedance_cli.framework.errors import CliError


def _short(task_id: str) -> str:
    # take chars after the first hyphen, first 6
    rest = task_id.split("-", 1)[-1]
    return rest[:6] or "task"


def _auto_name(task_id: str, created_at: int, ext: str) -> str:
    return f"{created_at}-{_short(task_id)}.{ext}"


def resolve_out_path(*, out: str | None, task_id: str, created_at: int, ext: str) -> Path:
    if out is None:
        return Path.cwd() / _auto_name(task_id, created_at, ext)
    # trailing slash → directory
    if out.endswith(("/", os.sep)):
        d = Path(out.rstrip("/" + os.sep)).expanduser()
        d.mkdir(parents=True, exist_ok=True)
        return d / _auto_name(task_id, created_at, ext)
    target = Path(out).expanduser()
    if not target.parent.exists():
        raise CliError(
            "IO_ERROR",
            f"parent directory does not exist: {target.parent} "
            f"(pass a path ending with '/' to auto-create, or mkdir it first)",
        )
    return target
