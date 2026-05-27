# seedance-cli

CLI for Volcengine Doubao Seedance video generation (`doubao-seedance-2-0` and friends), with an accompanying SKILL for Claude Code / AI agents.

## Install

```bash
# Recommended:
uv tool install seedance-cli

# Or with pipx:
pipx install seedance-cli

# Companion SKILL:
npx skills add zjandrew/seedance-cli -g -y
```

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

# Multimodal reference (seedance 2.0)
seedance-cli generate -p "..." --image a.png --image b.png --image c.png --out combo.mp4

# Video edit / extend (seedance 2.0)
seedance-cli generate -p "repaint walls blue" --video orig.mp4 --duration 5 --out edited.mp4

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
