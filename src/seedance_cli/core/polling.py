# src/seedance_cli/core/polling.py
from __future__ import annotations

import signal
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from seedance_cli.framework.errors import CliError


class _TasksAPI(Protocol):
    def get(self, task_id: str) -> Any: ...


@dataclass
class PollResult:
    status: str
    response: Any
    poll_count: int
    elapsed_seconds: float


_TERMINAL_OK = {"succeeded"}
_TERMINAL_FAIL = {"failed"}
_TERMINAL_EXPIRED = {"expired"}


def _to_dict(obj: Any) -> dict[str, Any]:
    # SDK responses come as dict-like, pydantic-model-like, or SimpleNamespace.
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    dump = getattr(obj, "model_dump", None)
    if callable(dump):
        return dump()  # type: ignore[no-any-return]
    return {k: v for k, v in vars(obj).items() if not k.startswith("_")}


def poll_until_done(
    tasks_api: _TasksAPI,
    *,
    task_id: str,
    interval: float = 10.0,
    timeout: float | None = None,
    on_status: Callable[[str, int], None] | None = None,
) -> PollResult:
    start = time.monotonic()
    poll_count = 0

    def _on_sigint(*_: Any) -> None:
        raise CliError(
            "POLL_CANCELLED",
            "polling interrupted",
            details={
                "task_id": task_id,
                "hint": f"resume with: seedance-cli task get {task_id} --wait --out <path>",
            },
        )

    prev = signal.signal(signal.SIGINT, _on_sigint)
    try:
        while True:
            resp = tasks_api.get(task_id)
            poll_count += 1
            status = getattr(resp, "status", None) or _to_dict(resp).get("status") or "unknown"
            if on_status:
                on_status(status, poll_count)
            if status in _TERMINAL_OK:
                return PollResult(
                    status=status,
                    response=resp,
                    poll_count=poll_count,
                    elapsed_seconds=time.monotonic() - start,
                )
            if status in _TERMINAL_FAIL:
                err = getattr(resp, "error", None)
                err_dict = _to_dict(err) if err is not None else {}
                raise CliError(
                    "TASK_FAILED",
                    f"task {task_id} failed",
                    details={"task_id": task_id, "error": err_dict},
                )
            if status in _TERMINAL_EXPIRED:
                raise CliError(
                    "TASK_EXPIRED",
                    f"task {task_id} expired",
                    details={"task_id": task_id},
                )
            elapsed = time.monotonic() - start
            if timeout is not None and elapsed >= timeout:
                raise CliError(
                    "POLL_TIMEOUT",
                    f"timeout after {elapsed:.0f}s; task still {status}",
                    details={
                        "task_id": task_id,
                        "last_status": status,
                        "elapsed_seconds": elapsed,
                    },
                )
            if interval > 0:
                time.sleep(interval)
    finally:
        signal.signal(signal.SIGINT, prev)
