# src/seedance_cli/framework/envelope.py
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from rich.console import Console
from rich.table import Table


@dataclass(frozen=True)
class Success:
    data: Any
    ok: Literal[True] = field(default=True, init=False)


@dataclass(frozen=True)
class Failure:
    code: str
    message: str
    details: dict[str, Any] | None = None
    ok: Literal[False] = field(default=False, init=False)


Envelope = Success | Failure


_TOKEN_RE = re.compile(r"\.([A-Za-z_][A-Za-z0-9_]*)|\[(\d+)\]")


def apply_jq(env: Success, expr: str) -> Success:
    """Minimal dotted-path / array-index filter. Not real jq."""
    if not expr.startswith("."):
        raise ValueError("jq expression must start with '.'")
    cur: Any = env.data
    for m in _TOKEN_RE.finditer(expr):
        key, idx = m.group(1), m.group(2)
        if cur is None:
            return Success(data=None)
        if key is not None:
            cur = cur.get(key) if isinstance(cur, dict) else None  # pyright: ignore[reportUnknownVariableType,reportUnknownMemberType]
        else:
            assert idx is not None
            try:
                cur = cur[int(idx)] if isinstance(cur, list) else None  # pyright: ignore[reportUnknownVariableType]
            except IndexError:
                cur = None
    return Success(data=cur)


def _to_dict(env: Envelope) -> dict[str, Any]:
    if isinstance(env, Success):
        return {"ok": True, "data": env.data}
    out: dict[str, Any] = {"ok": False, "error": {"code": env.code, "message": env.message}}
    if env.details is not None:
        out["error"]["details"] = env.details
    return out


def render(env: Envelope, fmt: Literal["json", "table"] = "json") -> str:
    if fmt == "json" or isinstance(env, Failure):
        return json.dumps(_to_dict(env), ensure_ascii=False, indent=2)
    return _render_table(env)


def _render_table(env: Success) -> str:
    data = env.data
    if isinstance(data, dict):
        console = Console(record=True, width=120)
        tbl = Table(show_header=False, box=None)
        tbl.add_column("key", style="cyan")
        tbl.add_column("value")
        for k, v in data.items():  # pyright: ignore[reportUnknownVariableType]
            tbl.add_row(str(k), json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v)  # pyright: ignore[reportUnknownArgumentType]
        console.print(tbl)
        return console.export_text().rstrip()
    return json.dumps(_to_dict(env), ensure_ascii=False, indent=2)
