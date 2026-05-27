# src/seedance_cli/commands/task.py
from __future__ import annotations

import os
from typing import Any

import click

import seedance_cli.core.client as _client_mod
from seedance_cli.__main__ import emit
from seedance_cli.commands.generate_wait import _to_data, wait_and_download
from seedance_cli.core.client import resolve_auth
from seedance_cli.core.config import load, resolve_profile
from seedance_cli.framework.envelope import Success


def _config_path():
    from seedance_cli.core.config import DEFAULT_CONFIG_PATH

    return DEFAULT_CONFIG_PATH


def _client(ctx: click.Context):
    cfg = load(_config_path())
    profile_name = resolve_profile(cli=ctx.obj.get("profile"), env=dict(os.environ), config=cfg)
    profile = cfg.profiles[profile_name]
    api_key, endpoint = resolve_auth(
        cli_api_key=ctx.obj.get("api_key"),
        cli_endpoint=ctx.obj.get("endpoint"),
        env=dict(os.environ),
        profile_api_key=profile.api_key,
        profile_endpoint=profile.endpoint,
    )
    return _client_mod.make_ark_client(api_key, endpoint)


@click.group(name="task")
def task() -> None:
    """Manage video generation tasks."""


@task.command("list")
@click.option(
    "--status",
    "statuses",
    multiple=True,
    type=click.Choice(["queued", "running", "succeeded", "failed", "expired"]),
)
@click.option("--model", default=None)
@click.option("--page-size", "page_size", type=int, default=None)
@click.option("--page-token", "page_token", default=None)
@click.pass_context
def task_list(
    ctx: click.Context,
    statuses: tuple[str, ...],
    model: str | None,
    page_size: int | None,
    page_token: str | None,
) -> None:
    client = _client(ctx)
    kwargs: dict[str, Any] = {}
    if statuses:
        kwargs["status"] = list(statuses)
    if model:
        kwargs["model"] = model
    if page_size:
        kwargs["page_size"] = page_size
    if page_token:
        kwargs["page_token"] = page_token
    resp = client.content_generation.tasks.list(**kwargs)
    items = getattr(resp, "items", None) or getattr(resp, "data", None) or []
    tasks_data = [_to_data(t) for t in items]
    emit(
        ctx,
        Success(
            data={
                "tasks": tasks_data,
                "next_page_token": getattr(resp, "next_page_token", None),
            }
        ),
    )


@task.command("get")
@click.argument("task_id")
@click.option("--wait", is_flag=True, default=False)
@click.option("--out", default=None)
@click.option("--poll-interval", "poll_interval", type=float, default=None)
@click.option("--timeout", type=float, default=None)
@click.pass_context
def task_get(
    ctx: click.Context,
    task_id: str,
    wait: bool,
    out: str | None,
    poll_interval: float | None,
    timeout: float | None,
) -> None:
    client = _client(ctx)
    if wait:
        wait_and_download(
            ctx=ctx,
            client=client,
            task_id=task_id,
            model_full="",
            out=out,
            out_last_frame=None,
            no_download=(out is None),
            return_last_frame=False,
            poll_interval=poll_interval,
            timeout=timeout,
            service_tier="default",
        )
        return
    resp = client.content_generation.tasks.get(task_id)
    emit(ctx, Success(data=_to_data(resp)))


@task.command("delete")
@click.argument("task_id")
@click.pass_context
def task_delete(ctx: click.Context, task_id: str) -> None:
    client = _client(ctx)
    client.content_generation.tasks.delete(task_id)
    emit(ctx, Success(data={"task_id": task_id, "deleted": True}))
