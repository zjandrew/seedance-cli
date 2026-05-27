# src/seedance_cli/__main__.py
from __future__ import annotations

import sys

import click

from seedance_cli.framework.envelope import Envelope, Success, apply_jq, render
from seedance_cli.framework.errors import exit_code_for, translate

__version__ = "0.1.0"


@click.group(name="seedance-cli", invoke_without_command=False)
@click.version_option(__version__, prog_name="seedance-cli")
@click.option("--endpoint", default=None, help="override endpoint for this invocation")
@click.option("--api-key", default=None, help="override API key for this invocation")
@click.option("--profile", default=None, help="select a saved profile")
@click.option("--format", "fmt", type=click.Choice(["json", "table"]), default="json")
@click.option("--jq", "jq_expr", default=None, help="dotted-path filter on envelope.data")
@click.option("--dry-run", is_flag=True, default=False)
@click.option("--verbose", is_flag=True, default=False)
@click.option("--yes", is_flag=True, default=False)
@click.pass_context
def root(
    ctx: click.Context,
    endpoint: str | None,
    api_key: str | None,
    profile: str | None,
    fmt: str,
    jq_expr: str | None,
    dry_run: bool,
    verbose: bool,
    yes: bool,
) -> None:
    """Volcengine Doubao Seedance video generation CLI."""
    ctx.ensure_object(dict)
    ctx.obj.update(
        {
            "endpoint": endpoint,
            "api_key": api_key,
            "profile": profile,
            "format": fmt,
            "jq": jq_expr,
            "dry_run": dry_run,
            "verbose": verbose,
            "yes": yes,
        }
    )


def emit(ctx: click.Context, env: Envelope) -> None:
    g = ctx.obj
    if isinstance(env, Success) and g.get("jq"):
        env = apply_jq(env, g["jq"])
    out = render(env, fmt=g.get("format") or "json")
    click.echo(out)


def _register_commands() -> None:
    # Commands are imported here (and registered via their own decorators) to
    # keep import side effects out of plain module load.
    from seedance_cli.commands import config as _config
    from seedance_cli.commands import generate as _generate
    from seedance_cli.commands import task as _task

    root.add_command(_generate.generate)
    root.add_command(_task.task)
    root.add_command(_config.config)


_register_commands()


def main() -> None:
    try:
        root.main(prog_name="seedance-cli", standalone_mode=False)
        sys.exit(0)
    except click.exceptions.UsageError as e:
        click.echo(e.format_message(), err=True)
        sys.exit(2)
    except click.exceptions.Abort:
        sys.exit(130)
    except SystemExit:
        raise
    except Exception as exc:  # top-level translator
        cli_err = translate(exc)
        click.echo(render(cli_err.to_envelope(), fmt="json"), err=True)
        if "--verbose" in sys.argv:
            import traceback

            traceback.print_exc(file=sys.stderr)
        sys.exit(exit_code_for(cli_err.code))


if __name__ == "__main__":
    main()
