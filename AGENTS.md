# AGENTS.md

CLI for Volcengine Doubao Seedance video generation (default model Seedance 2.5, `doubao-seedance-2-5-260628`; 2.0/1.x selectable via `-m`), plus a companion agent skill in `skills/seedance/`. Python 3.10+, Click + httpx + rich, managed with `uv`.

## Dev commands

```bash
uv sync --all-extras          # install with dev extras
uv run pytest                 # tests (unit + integration, all HTTP mocked — no real API calls)
uv run ruff check src tests   # lint
uv run pyright                # type check (strict mode)
```

## Architecture

Dependency direction: `commands/` → `core/` → `framework/`.

- `src/seedance_cli/framework/` — generic CLI plumbing with no Seedance knowledge: `envelope.py` (`Success`/`Failure` output envelope), `errors.py` (`CliError`, `EXIT_CODES`, exception translation).
- `src/seedance_cli/core/` — domain logic: config/profiles, Ark client, content-item building, polling, media I/O, output naming, download.
- `src/seedance_cli/commands/` — Click command wiring only; no business logic here.

## Contracts to keep in sync

- **Exit codes**: every failure is a `CliError` whose `code` maps through `EXIT_CODES` in `framework/errors.py`. Adding or changing a code means updating the exit-code table in `README.md`.
- **Companion skill**: `skills/seedance/SKILL.md` documents the CLI's flags and workflows for agents. When CLI flags or behavior change, update the skill and bump the `version` in its frontmatter.
- **Release version**: bump `version` in `pyproject.toml` with each user-visible fix. Commit style is conventional commits with the bump noted, e.g. `fix(media_io): pass asset:// URIs through; bump 1.0.3`.

## Testing

- `tests/unit/` mirrors the `src/seedance_cli/` layout.
- `tests/integration/` drives Click commands end to end via `CliRunner`, with HTTP mocked by `respx`.

## Notes

- The PyPI distribution is `zjandrew-seedance-cli` (the bare name was taken); the installed binary is still `seedance-cli`.
- `docs/superpowers/` holds the original implementation plan and design spec.

## Agent skills

### Issue tracker

Issues live in this repo's GitHub Issues (`zjandrew/seedance-cli`), operated via the `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-role vocabulary: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout — `CONTEXT.md` and `docs/adr/` at the repo root (created lazily; absence is fine). See `docs/agents/domain.md`.
