# src/seedance_cli/commands/generate_wait.py
from __future__ import annotations

import sys
from typing import Any

import click
from rich.console import Console

from seedance_cli.__main__ import emit
from seedance_cli.core.download import download
from seedance_cli.core.naming import resolve_out_path
from seedance_cli.core.polling import poll_until_done
from seedance_cli.framework.envelope import Success


def _extract_field(resp: Any, *names: str) -> Any:
    for n in names:
        v = getattr(resp, n, None)
        if v is not None:
            return v
    content = getattr(resp, "content", None)
    if content is None:
        return None
    for n in names:
        v = getattr(content, n, None)
        if v is not None:
            return v
    return None


def response_to_data(resp: Any) -> dict[str, Any]:
    """Translate the SDK response object into the envelope-friendly dict."""
    data = {
        "task_id": getattr(resp, "id", None),
        "status": getattr(resp, "status", None),
        "model": getattr(resp, "model", None),
        "video_url": _extract_field(resp, "video_url"),
        "last_frame_url": _extract_field(resp, "last_frame_url"),
        "duration": getattr(resp, "duration", None),
        "ratio": getattr(resp, "ratio", None),
        "resolution": getattr(resp, "resolution", None),
        "framespersecond": getattr(resp, "framespersecond", None),
        "seed": getattr(resp, "seed", None),
        "service_tier": getattr(resp, "service_tier", None),
        "created_at": getattr(resp, "created_at", None),
        "updated_at": getattr(resp, "updated_at", None),
    }
    usage = getattr(resp, "usage", None)
    if usage is not None:
        data["usage"] = {
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }
    return {k: v for k, v in data.items() if v is not None}


def wait_and_download(
    *,
    ctx: click.Context,
    client: Any,
    task_id: str,
    model_full: str,
    out: str | None,
    out_last_frame: str | None,
    no_download: bool,
    return_last_frame: bool,
    poll_interval: float | None,
    timeout: float | None,
    service_tier: str,
) -> None:
    interval = (
        poll_interval if poll_interval is not None else (60.0 if service_tier == "flex" else 10.0)
    )

    console = Console(file=sys.stderr, force_terminal=False)
    with console.status("[cyan]queued...") as status:

        def on_status(s: str, n: int) -> None:
            status.update(f"[cyan]{s} — poll #{n}")

        result = poll_until_done(
            client.content_generation.tasks,
            task_id=task_id,
            interval=interval,
            timeout=timeout,
            on_status=on_status,
        )

    data = response_to_data(result.response)
    data["elapsed_seconds"] = round(result.elapsed_seconds, 1)
    data["poll_count"] = result.poll_count
    data["model"] = data.get("model") or model_full

    video_url = data.get("video_url")
    last_frame_url = data.get("last_frame_url")

    if not no_download and video_url:
        created_at = int(data.get("created_at") or 0)
        path = resolve_out_path(out=out, task_id=task_id, created_at=created_at, ext="mp4")
        download(url=video_url, out=path)
        data["video_path"] = str(path)

    if return_last_frame and last_frame_url and out_last_frame is not None:
        path = resolve_out_path(
            out=out_last_frame,
            task_id=task_id,
            created_at=int(data.get("created_at") or 0),
            ext="png",
        )
        download(url=last_frame_url, out=path)
        data["last_frame_path"] = str(path)

    emit(ctx, Success(data=data))
