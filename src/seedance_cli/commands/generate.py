# src/seedance_cli/commands/generate.py
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal, cast

import click

import seedance_cli.core.client as _client_mod
from seedance_cli.__main__ import emit
from seedance_cli.core.client import (
    DEFAULT_MODEL,
    expand_model,
    resolve_auth,
)
from seedance_cli.core.config import load, resolve_profile
from seedance_cli.core.content import (
    VALID_IMAGE_ROLES,
    VALID_VIDEO_ROLES,
    RequestParams,
    build_request,
)
from seedance_cli.core.media_io import RequestBudget, parse_ref
from seedance_cli.framework.envelope import Success
from seedance_cli.framework.errors import CliError


def _config_path() -> Path:
    # Lazy import so tmp_config fixture's monkeypatch on DEFAULT_CONFIG_PATH wins.
    from seedance_cli.core.config import DEFAULT_CONFIG_PATH

    return DEFAULT_CONFIG_PATH


def _redact_base64(req: dict[str, Any]) -> dict[str, Any]:
    """Replace data: URIs with <base64 NNKB> placeholders for safe stdout printing."""

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items()}  # pyright: ignore[reportUnknownVariableType]
        if isinstance(node, list):
            return [walk(x) for x in node]  # pyright: ignore[reportUnknownVariableType]
        if isinstance(node, str) and node.startswith("data:") and ";base64," in node:
            kb = len(node) * 3 // 4 // 1024
            return f"<base64 {kb}KB>"
        return node

    return walk(req)


@click.command("generate")
@click.option("-p", "--prompt", "prompt_text", default=None, help="text prompt")
@click.option("--image", "images", multiple=True, help="PATH_OR_URL[:role]")
@click.option("--video", "videos", multiple=True, help="PATH_OR_URL[:role]")
@click.option("--audio", "audios", multiple=True, help="PATH_OR_URL")
@click.option(
    "-m",
    "--model",
    default=None,
    help="model id or alias (2.0, 2.0-fast, 1.5-pro, 1.0-pro, 1.0-pro-fast)",
)
@click.option("--ratio", default=None)
@click.option(
    "--resolution",
    default=None,
    type=click.Choice(["480p", "720p", "1080p"]),
)
@click.option("--duration", default=None, type=int)
@click.option("--frames", default=None, type=int)
@click.option("--seed", default=None, type=int)
@click.option("--camera-fixed/--no-camera-fixed", "camera_fixed", default=None)
@click.option("--watermark/--no-watermark", default=False)
@click.option("--generate-audio/--no-generate-audio", "generate_audio", default=None)
@click.option("--return-last-frame", "return_last_frame", is_flag=True, default=False)
@click.option(
    "--service-tier",
    "service_tier",
    type=click.Choice(["default", "flex"]),
    default=None,
)
@click.option("--execution-expires-after", "execution_expires_after", type=int, default=None)
@click.option("--callback-url", "callback_url", default=None)
@click.option(
    "--from-json",
    "from_json",
    type=click.Path(exists=True),
    default=None,
    help="load request body from JSON; other flags still override top-level fields",
)
@click.option("--out", default=None, help="output mp4 path (trailing / treats as dir)")
@click.option("--out-last-frame", "out_last_frame", default=None)
@click.option("--async", "is_async", is_flag=True, default=False)
@click.option("--no-download", "no_download", is_flag=True, default=False)
@click.option("--poll-interval", "poll_interval", type=float, default=None)
@click.option("--timeout", type=float, default=None)
@click.pass_context
def generate(
    ctx: click.Context,
    prompt_text: str | None,
    images: tuple[str, ...],
    videos: tuple[str, ...],
    audios: tuple[str, ...],
    model: str | None,
    ratio: str | None,
    resolution: str | None,
    duration: int | None,
    frames: int | None,
    seed: int | None,
    camera_fixed: bool | None,
    watermark: bool,
    generate_audio: bool | None,
    return_last_frame: bool,
    service_tier: str | None,
    execution_expires_after: int | None,
    callback_url: str | None,
    from_json: str | None,
    out: str | None,
    out_last_frame: str | None,
    is_async: bool,
    no_download: bool,
    poll_interval: float | None,
    timeout: float | None,
) -> None:
    """Create a video generation task."""
    g = ctx.obj

    image_refs = [parse_ref(a, valid_roles=VALID_IMAGE_ROLES) for a in images]
    video_refs = [parse_ref(a, valid_roles=VALID_VIDEO_ROLES) for a in videos]
    audio_refs = [parse_ref(a, valid_roles=set()) for a in audios]

    cfg = load(_config_path())
    profile_name = resolve_profile(cli=g.get("profile"), env=dict(os.environ), config=cfg)
    profile = cfg.profiles[profile_name]
    chosen_model = model or profile.default_model or DEFAULT_MODEL

    base_request: dict[str, Any] = {}
    if from_json:
        base_request = json.loads(Path(from_json).read_text())

    params = RequestParams(
        model=chosen_model,
        ratio=ratio,
        resolution=resolution,
        duration=duration,
        frames=frames,
        seed=seed,
        camera_fixed=camera_fixed,
        watermark=watermark,
        generate_audio=generate_audio,
        return_last_frame=return_last_frame,
        service_tier=cast("Literal['default', 'flex'] | None", service_tier),
        execution_expires_after=execution_expires_after,
        callback_url=callback_url,
    )

    budget = RequestBudget()
    built = build_request(
        params=params,
        text=prompt_text,
        images=image_refs,
        videos=video_refs,
        audios=audio_refs,
        budget=budget,
    )
    request_body: dict[str, Any] = {**base_request, **built}

    if g.get("dry_run"):
        emit(
            ctx,
            Success(
                data={
                    "request": _redact_base64(request_body),
                    "would_call": "content_generation.tasks.create",
                }
            ),
        )
        return

    api_key, endpoint = resolve_auth(
        cli_api_key=g.get("api_key"),
        cli_endpoint=g.get("endpoint"),
        env=dict(os.environ),
        profile_api_key=profile.api_key,
        profile_endpoint=profile.endpoint,
    )
    client = _client_mod.make_ark_client(api_key, endpoint)
    created = client.content_generation.tasks.create(**request_body)
    task_id = getattr(created, "id", None)
    if not task_id:
        raise CliError("INTERNAL", "API did not return a task id")

    if is_async:
        emit(
            ctx,
            Success(
                data={
                    "task_id": task_id,
                    "status": "queued",
                    "model": expand_model(chosen_model),
                }
            ),
        )
        return

    # Blocking + download — implemented in Task 15.
    from seedance_cli.commands.generate_wait import wait_and_download

    wait_and_download(
        ctx=ctx,
        client=client,
        task_id=task_id,
        model_full=expand_model(chosen_model),
        out=out,
        out_last_frame=out_last_frame,
        no_download=no_download,
        return_last_frame=return_last_frame,
        poll_interval=poll_interval,
        timeout=timeout,
        service_tier=service_tier or "default",
    )
