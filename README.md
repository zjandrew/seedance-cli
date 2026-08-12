# seedance-cli

CLI for Volcengine Doubao Seedance video generation (Seedance 2.5 by default, 2.0/1.x selectable), with an accompanying SKILL for Claude Code / AI agents.

## Install

```bash
# Recommended:
uv tool install zjandrew-seedance-cli

# Or with pipx:
pipx install zjandrew-seedance-cli

# Companion SKILL:
npx skills add zjandrew/seedance-cli -g -y
```

The PyPI distribution is named `zjandrew-seedance-cli` because the bare
`seedance-cli` name was already taken. After install you still invoke it as
`seedance-cli` (the binary name is unchanged).

Local development:

```bash
git clone https://github.com/zjandrew/seedance-cli.git
cd seedance-cli
uv sync --all-extras
uv run seedance-cli --version
```

## Configure

```bash
# Interactive wizard (creates ~/.seedance-cli/config.json, chmod 600):
seedance-cli config init

# Or env vars:
export ARK_API_KEY=...
export SEEDANCE_ENDPOINT=https://ark.cn-beijing.volces.com/api/v3   # optional

# Or programmatic:
seedance-cli config set api_key ...
seedance-cli config set endpoint https://...
```

Priority: CLI flag > env var > config file > built-in default.

### Multiple profiles

```bash
seedance-cli config list
seedance-cli config add prod
seedance-cli config use prod
seedance-cli --profile prod generate -p "..."
```

## Models

> **Since v1.1.0 the default model is Seedance 2.5.** Same commands now hit
> `doubao-seedance-2-5-260628` (different capabilities and pricing than 2.0).
> Pin a profile back with `seedance-cli config set default_model 2.0`, or
> per-invocation with `-m 2.0`.

`-m/--model` accepts an alias below or any full `doubao-seedance-*` id (unknown
ids pass through for forward compatibility).

| Alias | Model ID | Capability highlights |
|---|---|---|
| `2.5` (default) | `doubao-seedance-2-5-260628` | 480p/720p; duration 4–30s or `-1`; up to 30 images / 10 videos / 10 audios; audio-only input; `--task-type` / `--output-format` |
| `2.0` | `doubao-seedance-2-0-260128` | 480p–4k; 4–15s or `-1`; 9 images / 3 videos / 3 audios |
| `2.0-fast` | `doubao-seedance-2-0-fast-260128` | 480p/720p; 4–15s or `-1` |
| `2.0-mini` | `doubao-seedance-2-0-mini-260615` | 480p/720p; 4–15s or `-1` |
| `1.5-pro` | `doubao-seedance-1-5-pro-251215` | 480p–1080p; 4–12s or `-1`; `--camera-fixed`, `--service-tier flex`, `--seed` |
| `1.0-pro` | `doubao-seedance-1-0-pro-250528` | 480p–1080p; 2–12s; `--frames`, `--seed` |
| `1.0-pro-fast` | `doubao-seedance-1-0-pro-fast-251015` | 480p–1080p; 2–12s; `--frames`, `--seed` |

`--seed`, `--frames`, `--camera-fixed` and `--service-tier flex` are 1.x-only;
the CLI rejects them on 2.x up front. On 2.5, first-frame / first+last-frame
tasks (and explicit `--task-type edit/extend`) force `ratio=adaptive` — drop
`--ratio` and the model aligns it to your input.

## Usage

```bash
# Text → video
seedance-cli generate -p "a tabby cat yawning at the camera" --ratio 16:9 --duration 5 --out cat.mp4

# Image → video (first frame)
seedance-cli generate -p "girl smiles" --image start.png --duration 5 --out smile.mp4

# First + last frame
seedance-cli generate -p "360-degree pan" \
  --image first.png:first_frame --image last.png:last_frame \
  --duration 5 --out pan.mp4

# Multimodal reference (seedance 2.x; up to 30 images on 2.5)
seedance-cli generate -p "..." --image a.png --image b.png --image c.png --out combo.mp4

# Video edit / extend (seedance 2.x)
seedance-cli generate -p "repaint walls blue" --video orig.mp4 --duration 5 --out edited.mp4

# Seedance 2.5: declare the task type to fail fast (sync 4xx instead of a
# deferred rejection), and pick the mov container for edit/extend chains
seedance-cli generate -p "repaint walls blue" -m 2.5 --video orig.mp4 \
  --task-type edit --output-format mov --out edited.mov

# Async + polling
seedance-cli generate -p "..." --async
seedance-cli task list --status running --status queued
seedance-cli task get cgt-2026-... --wait --out result.mp4

# Dry run (prints the request body, no API call)
seedance-cli generate -p "..." --dry-run
```

## SKILL

`skills/seedance/SKILL.md` ships in this repo. Install for Claude Code:

```bash
npx skills add zjandrew/seedance-cli -g -y
```

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success |
| 2 | INVALID_INPUT / CONFIG_MISSING |
| 3 | IO_ERROR |
| 4 | ARK_API_ERROR |
| 5 | NETWORK_ERROR |
| 6 | TASK_FAILED |
| 7 | TASK_EXPIRED |
| 8 | POLL_TIMEOUT |
| 9 | POLL_CANCELLED (Ctrl-C) |
| 10 | INTERNAL |

## License

MIT
