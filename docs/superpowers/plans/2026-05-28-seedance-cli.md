# seedance-cli Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Python CLI (`seedance-cli`) that wraps Volcengine Doubao Seedance video generation API plus a companion Claude Code SKILL, mirroring the gpt-image-cli architecture.

**Architecture:** Click-based CLI with three layers: `framework/` (envelope + errors, domain-agnostic), `core/` (Volcengine SDK wrapper, config, content folding, polling, download), `commands/` (generate/task/config). One unified `generate` command folds text/image/video/audio inputs into the API's `content[]` array. Default blocks-and-downloads (polling); `--async` opts out.

**Tech Stack:** Python ≥ 3.10, `uv` + `hatchling`, `click`, `volcengine-python-sdk[ark]`, `httpx`, `rich`. Tests: `pytest`, `click.testing.CliRunner`, `respx` for HTTP, `FakeArk` fixture for SDK boundary.

**Reference spec:** `docs/superpowers/specs/2026-05-28-seedance-cli-design.md` — read it first, every task assumes it.

---

## Task 1: Project skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `src/seedance_cli/__init__.py`
- Create: `src/seedance_cli/__main__.py` (stub)
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`, `tests/unit/core/__init__.py`, `tests/unit/framework/__init__.py`
- Create: `tests/integration/__init__.py`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "seedance-cli"
version = "0.1.0"
description = "CLI for Volcengine Doubao Seedance video generation, with a companion Claude Code SKILL"
readme = "README.md"
requires-python = ">=3.10"
license = "MIT"
authors = [{ name = "zjandrew" }]
dependencies = [
  "click>=8.1",
  "httpx>=0.27",
  "rich>=13",
  "volcengine-python-sdk[ark]>=1.0.98",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-cov", "ruff", "pyright", "respx"]

[project.scripts]
seedance-cli = "seedance_cli.__main__:main"

[tool.hatch.build.targets.wheel]
packages = ["src/seedance_cli"]

[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]

[tool.pyright]
include = ["src", "tests"]
pythonVersion = "3.10"
typeCheckingMode = "strict"
reportMissingTypeStubs = false

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"
```

- [ ] **Step 2: Write stub `__main__.py`**

```python
# src/seedance_cli/__main__.py
def main() -> None:
    raise SystemExit("not implemented yet")

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Create empty `__init__.py` files**

```bash
touch src/seedance_cli/__init__.py \
      tests/__init__.py \
      tests/unit/__init__.py \
      tests/unit/core/__init__.py \
      tests/unit/framework/__init__.py \
      tests/integration/__init__.py
mkdir -p tests/fixtures
```

- [ ] **Step 4: Bootstrap the dev environment and verify install**

Run:
```bash
uv sync --all-extras
uv run seedance-cli
```

Expected: command runs, exits with status 1 and message "not implemented yet". This confirms console_scripts wiring is correct.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/ tests/
git commit -m "feat(scaffold): project skeleton + console_scripts entry"
```

---

## Task 2: framework/envelope.py — output envelope + jq path filter + table render

**Files:**
- Create: `src/seedance_cli/framework/__init__.py`
- Create: `src/seedance_cli/framework/envelope.py`
- Create: `tests/unit/framework/test_envelope.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/framework/test_envelope.py
import json
import pytest
from seedance_cli.framework.envelope import Success, Failure, render, apply_jq


def test_success_renders_json():
    out = render(Success(data={"task_id": "cgt-1", "status": "succeeded"}), fmt="json")
    parsed = json.loads(out)
    assert parsed == {"ok": True, "data": {"task_id": "cgt-1", "status": "succeeded"}}


def test_failure_renders_json_with_details():
    out = render(Failure(code="INVALID_INPUT", message="bad ratio", details={"flag": "--ratio"}), fmt="json")
    parsed = json.loads(out)
    assert parsed == {"ok": False, "error": {"code": "INVALID_INPUT", "message": "bad ratio", "details": {"flag": "--ratio"}}}


def test_failure_renders_json_without_details():
    out = render(Failure(code="NETWORK_ERROR", message="boom"), fmt="json")
    parsed = json.loads(out)
    assert "details" not in parsed["error"]


def test_apply_jq_simple_path():
    env = Success(data={"task_id": "cgt-1", "nested": {"video_url": "https://x"}})
    out = apply_jq(env, ".nested.video_url")
    assert out.data == "https://x"


def test_apply_jq_array_index():
    env = Success(data={"tasks": [{"id": "a"}, {"id": "b"}]})
    out = apply_jq(env, ".tasks[1].id")
    assert out.data == "b"


def test_apply_jq_unknown_path_returns_none():
    env = Success(data={"a": 1})
    out = apply_jq(env, ".nope.missing")
    assert out.data is None


def test_render_table_dict_kv():
    out = render(Success(data={"task_id": "cgt-1", "duration": 5}), fmt="table")
    assert "task_id" in out and "cgt-1" in out and "duration" in out


def test_render_table_falls_back_to_json_for_scalar():
    out = render(Success(data="raw-string"), fmt="table")
    assert "raw-string" in out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/framework/test_envelope.py -v`
Expected: all FAIL with `ModuleNotFoundError: No module named 'seedance_cli.framework.envelope'`.

- [ ] **Step 3: Write the implementation**

```python
# src/seedance_cli/framework/__init__.py
```

```python
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
            cur = cur.get(key) if isinstance(cur, dict) else None
        else:
            assert idx is not None
            try:
                cur = cur[int(idx)] if isinstance(cur, list) else None
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
        for k, v in data.items():
            tbl.add_row(str(k), json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v)
        console.print(tbl)
        return console.export_text().rstrip()
    return json.dumps(_to_dict(env), ensure_ascii=False, indent=2)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/framework/test_envelope.py -v`
Expected: 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/seedance_cli/framework/ tests/unit/framework/test_envelope.py
git commit -m "feat(framework): envelope renderer + dotted-path jq filter"
```

---

## Task 3: framework/errors.py — CliError + exit-code map + SDK exception translator

**Files:**
- Create: `src/seedance_cli/framework/errors.py`
- Create: `tests/unit/framework/test_errors.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/framework/test_errors.py
import httpx
import pytest
from seedance_cli.framework.errors import CliError, EXIT_CODES, exit_code_for, translate


def test_cli_error_to_envelope():
    err = CliError("INVALID_INPUT", "bad --ratio", details={"flag": "--ratio"})
    env = err.to_envelope()
    assert env.code == "INVALID_INPUT"
    assert env.message == "bad --ratio"
    assert env.details == {"flag": "--ratio"}


def test_exit_code_for_known_codes():
    assert exit_code_for("INVALID_INPUT") == 2
    assert exit_code_for("CONFIG_MISSING") == 2
    assert exit_code_for("IO_ERROR") == 3
    assert exit_code_for("ARK_API_ERROR") == 4
    assert exit_code_for("NETWORK_ERROR") == 5
    assert exit_code_for("TASK_FAILED") == 6
    assert exit_code_for("TASK_EXPIRED") == 7
    assert exit_code_for("POLL_TIMEOUT") == 8
    assert exit_code_for("POLL_CANCELLED") == 9
    assert exit_code_for("INTERNAL") == 10


def test_exit_code_for_unknown_falls_back_to_internal():
    assert exit_code_for("MYSTERY") == 10


def test_translate_passes_cli_error_through():
    src = CliError("INVALID_INPUT", "x")
    assert translate(src) is src


def test_translate_oserror_to_io_error():
    err = translate(PermissionError("no perms"))
    assert err.code == "IO_ERROR"
    assert "no perms" in err.message


def test_translate_httpx_connect_to_network_error():
    err = translate(httpx.ConnectError("connection refused"))
    assert err.code == "NETWORK_ERROR"


def test_translate_httpx_timeout_to_network_error():
    err = translate(httpx.ReadTimeout("timed out"))
    assert err.code == "NETWORK_ERROR"


def test_translate_unknown_to_internal():
    err = translate(RuntimeError("???"))
    assert err.code == "INTERNAL"
    assert "???" in err.message
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/framework/test_errors.py -v`
Expected: all FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

```python
# src/seedance_cli/framework/errors.py
from __future__ import annotations

from typing import Any

import httpx

from seedance_cli.framework.envelope import Failure


EXIT_CODES: dict[str, int] = {
    "INVALID_INPUT": 2,
    "CONFIG_MISSING": 2,
    "IO_ERROR": 3,
    "ARK_API_ERROR": 4,
    "NETWORK_ERROR": 5,
    "TASK_FAILED": 6,
    "TASK_EXPIRED": 7,
    "POLL_TIMEOUT": 8,
    "POLL_CANCELLED": 9,
    "INTERNAL": 10,
}


class CliError(Exception):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def to_envelope(self) -> Failure:
        return Failure(code=self.code, message=self.message, details=self.details)


def exit_code_for(code: str) -> int:
    return EXIT_CODES.get(code, EXIT_CODES["INTERNAL"])


def translate(exc: Exception) -> CliError:
    if isinstance(exc, CliError):
        return exc
    if isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout)):
        return CliError("NETWORK_ERROR", str(exc) or exc.__class__.__name__)
    # Ark SDK exception — duck-typed to avoid hard import dependency in framework layer
    if exc.__class__.__name__ in {"ArkAPIError", "ArkException"}:
        details: dict[str, Any] = {}
        for attr in ("status_code", "code", "message", "request_id"):
            if hasattr(exc, attr):
                details[attr] = getattr(exc, attr)
        return CliError("ARK_API_ERROR", str(exc), details=details or None)
    if isinstance(exc, (OSError, PermissionError, FileNotFoundError)):
        return CliError("IO_ERROR", str(exc))
    return CliError("INTERNAL", str(exc) or exc.__class__.__name__)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/framework/test_errors.py -v`
Expected: 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/seedance_cli/framework/errors.py tests/unit/framework/test_errors.py
git commit -m "feat(framework): CliError + exit code map + SDK exception translator"
```

---

## Task 4: core/client.py — model aliases + ArkLike Protocol + auth resolver

**Files:**
- Create: `src/seedance_cli/core/__init__.py`
- Create: `src/seedance_cli/core/client.py`
- Create: `tests/unit/core/test_client.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/core/test_client.py
import pytest
from seedance_cli.core.client import (
    DEFAULT_ENDPOINT,
    DEFAULT_MODEL,
    MODEL_ALIASES,
    expand_model,
    resolve_auth,
)
from seedance_cli.framework.errors import CliError


def test_expand_known_alias():
    assert expand_model("2.0") == "doubao-seedance-2-0-260128"
    assert expand_model("2.0-fast") == "doubao-seedance-2-0-fast-260128"
    assert expand_model("1.5-pro") == "doubao-seedance-1-5-pro-251215"
    assert expand_model("1.0-pro") == "doubao-seedance-1-0-pro-250528"
    assert expand_model("1.0-pro-fast") == "doubao-seedance-1-0-pro-fast-251015"


def test_expand_full_id_passes_through():
    assert expand_model("doubao-seedance-2-0-260128") == "doubao-seedance-2-0-260128"


def test_expand_unknown_short_alias_raises():
    with pytest.raises(CliError) as ei:
        expand_model("3.0")
    assert ei.value.code == "INVALID_INPUT"


def test_resolve_auth_flag_wins():
    api_key, endpoint = resolve_auth(
        cli_api_key="flag-key", cli_endpoint=None,
        env={"ARK_API_KEY": "env-key"},
        profile_api_key="profile-key", profile_endpoint="profile-endpoint",
    )
    assert api_key == "flag-key"
    assert endpoint == "profile-endpoint"


def test_resolve_auth_env_beats_profile():
    api_key, endpoint = resolve_auth(
        cli_api_key=None, cli_endpoint=None,
        env={"ARK_API_KEY": "env-key", "SEEDANCE_ENDPOINT": "env-endpoint"},
        profile_api_key="profile-key", profile_endpoint="profile-endpoint",
    )
    assert api_key == "env-key"
    assert endpoint == "env-endpoint"


def test_resolve_auth_profile_used_when_no_flag_or_env():
    api_key, endpoint = resolve_auth(
        cli_api_key=None, cli_endpoint=None, env={},
        profile_api_key="profile-key", profile_endpoint="profile-endpoint",
    )
    assert api_key == "profile-key"
    assert endpoint == "profile-endpoint"


def test_resolve_auth_missing_key_raises_config_missing():
    with pytest.raises(CliError) as ei:
        resolve_auth(cli_api_key=None, cli_endpoint=None, env={}, profile_api_key=None, profile_endpoint=None)
    assert ei.value.code == "CONFIG_MISSING"


def test_resolve_auth_endpoint_falls_back_to_default():
    _, endpoint = resolve_auth(
        cli_api_key="k", cli_endpoint=None, env={}, profile_api_key=None, profile_endpoint=None,
    )
    assert endpoint == DEFAULT_ENDPOINT


def test_default_model_constant():
    assert DEFAULT_MODEL in MODEL_ALIASES.values()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/core/test_client.py -v`
Expected: all FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

```python
# src/seedance_cli/core/__init__.py
```

```python
# src/seedance_cli/core/client.py
from __future__ import annotations

from typing import Any, Protocol

from seedance_cli.framework.errors import CliError


DEFAULT_ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL = "doubao-seedance-2-0-260128"

MODEL_ALIASES: dict[str, str] = {
    "2.0":          "doubao-seedance-2-0-260128",
    "2.0-fast":     "doubao-seedance-2-0-fast-260128",
    "1.5-pro":      "doubao-seedance-1-5-pro-251215",
    "1.0-pro":      "doubao-seedance-1-0-pro-250528",
    "1.0-pro-fast": "doubao-seedance-1-0-pro-fast-251015",
}

_FULL_IDS = set(MODEL_ALIASES.values())


class ArkLike(Protocol):
    @property
    def content_generation(self) -> Any: ...


def expand_model(name: str) -> str:
    if name in _FULL_IDS:
        return name
    if name in MODEL_ALIASES:
        return MODEL_ALIASES[name]
    if name.startswith("doubao-seedance-"):
        # Forward-compat: trust full IDs we don't recognize yet
        return name
    raise CliError(
        "INVALID_INPUT",
        f"unknown model {name!r}",
        details={"flag": "--model", "known_aliases": list(MODEL_ALIASES.keys())},
    )


def resolve_auth(
    *,
    cli_api_key: str | None,
    cli_endpoint: str | None,
    env: dict[str, str],
    profile_api_key: str | None,
    profile_endpoint: str | None,
) -> tuple[str, str]:
    api_key = cli_api_key or env.get("ARK_API_KEY") or profile_api_key
    if not api_key:
        raise CliError(
            "CONFIG_MISSING",
            "no API key found. set ARK_API_KEY env or run: seedance-cli config init",
        )
    endpoint = cli_endpoint or env.get("SEEDANCE_ENDPOINT") or profile_endpoint or DEFAULT_ENDPOINT
    return api_key, endpoint


def make_ark_client(api_key: str, endpoint: str) -> ArkLike:
    # Imported lazily so unit tests that mock this factory don't need the SDK at import time
    from volcenginesdkarkruntime import Ark
    return Ark(api_key=api_key, base_url=endpoint)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/core/test_client.py -v`
Expected: 9 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/seedance_cli/core/__init__.py src/seedance_cli/core/client.py tests/unit/core/test_client.py
git commit -m "feat(core): model aliases + ArkLike Protocol + auth resolver"
```

---

## Task 5: core/config.py — profile schema + read/write + chmod 600 + mask

**Files:**
- Create: `src/seedance_cli/core/config.py`
- Create: `tests/unit/core/test_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/core/test_config.py
import json
import os
import stat
import pytest
from pathlib import Path
from seedance_cli.core.config import (
    Config, Profile, DEFAULT_ENDPOINT, load, save, mask_api_key, resolve_profile,
)
from seedance_cli.framework.errors import CliError


def test_load_returns_empty_when_no_file(tmp_path: Path):
    cfg = load(tmp_path / "missing.json")
    assert cfg.version == 1
    assert cfg.active == "default"
    assert "default" in cfg.profiles
    assert cfg.profiles["default"].api_key is None
    assert cfg.profiles["default"].endpoint == DEFAULT_ENDPOINT


def test_save_then_load_roundtrip(tmp_path: Path):
    cfg = Config(active="prod", profiles={"prod": Profile(api_key="sk-1234567890", default_model="2.0")})
    path = tmp_path / "config.json"
    save(cfg, path)
    loaded = load(path)
    assert loaded.active == "prod"
    assert loaded.profiles["prod"].api_key == "sk-1234567890"
    assert loaded.profiles["prod"].default_model == "2.0"


def test_save_chmods_to_600(tmp_path: Path):
    path = tmp_path / "config.json"
    save(Config(profiles={"default": Profile(api_key="k")}), path)
    mode = stat.S_IMODE(path.stat().st_mode)
    assert mode == 0o600


def test_save_creates_parent_dirs(tmp_path: Path):
    path = tmp_path / "nested" / "deep" / "config.json"
    save(Config(profiles={"default": Profile()}), path)
    assert path.exists()


def test_mask_api_key():
    assert mask_api_key("sk-abcdefghij1234") == "sk-***1234"
    assert mask_api_key("short") == "***rt"
    assert mask_api_key("") == ""
    assert mask_api_key(None) == ""


def test_resolve_profile_flag_wins():
    cfg = Config(active="b", profiles={"a": Profile(), "b": Profile(), "c": Profile()})
    name = resolve_profile(cli="a", env={"SEEDANCE_PROFILE": "c"}, config=cfg)
    assert name == "a"


def test_resolve_profile_env_beats_active():
    cfg = Config(active="b", profiles={"b": Profile(), "c": Profile()})
    name = resolve_profile(cli=None, env={"SEEDANCE_PROFILE": "c"}, config=cfg)
    assert name == "c"


def test_resolve_profile_falls_back_to_active():
    cfg = Config(active="b", profiles={"a": Profile(), "b": Profile()})
    name = resolve_profile(cli=None, env={}, config=cfg)
    assert name == "b"


def test_resolve_profile_unknown_name_raises(tmp_path: Path):
    cfg = Config(active="default", profiles={"default": Profile()})
    with pytest.raises(CliError) as ei:
        resolve_profile(cli="nope", env={}, config=cfg)
    assert ei.value.code == "INVALID_INPUT"


def test_load_corrupt_json_raises_io_error(tmp_path: Path):
    path = tmp_path / "config.json"
    path.write_text("{not json")
    with pytest.raises(CliError) as ei:
        load(path)
    assert ei.value.code == "IO_ERROR"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/core/test_config.py -v`
Expected: all FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

```python
# src/seedance_cli/core/config.py
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from seedance_cli.framework.errors import CliError


DEFAULT_ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_CONFIG_PATH = Path.home() / ".seedance-cli" / "config.json"


@dataclass
class Profile:
    api_key: str | None = None
    endpoint: str = DEFAULT_ENDPOINT
    default_model: str | None = None


@dataclass
class Config:
    version: int = 1
    active: str = "default"
    profiles: dict[str, Profile] = field(default_factory=lambda: {"default": Profile()})


def load(path: Path = DEFAULT_CONFIG_PATH) -> Config:
    if not path.exists():
        return Config()
    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        raise CliError("IO_ERROR", f"config file is not valid JSON: {path} ({e})") from e
    except OSError as e:
        raise CliError("IO_ERROR", f"cannot read config: {path} ({e})") from e

    profiles_raw: dict[str, Any] = raw.get("profiles") or {}
    profiles = {
        name: Profile(
            api_key=p.get("api_key"),
            endpoint=p.get("endpoint", DEFAULT_ENDPOINT),
            default_model=p.get("default_model"),
        )
        for name, p in profiles_raw.items()
    }
    if not profiles:
        profiles = {"default": Profile()}
    return Config(
        version=raw.get("version", 1),
        active=raw.get("active", "default"),
        profiles=profiles,
    )


def save(cfg: Config, path: Path = DEFAULT_CONFIG_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = {
        "version": cfg.version,
        "active": cfg.active,
        "profiles": {name: asdict(p) for name, p in cfg.profiles.items()},
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(serialized, indent=2, ensure_ascii=False))
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def mask_api_key(key: str | None) -> str:
    if not key:
        return ""
    if len(key) <= 6:
        return "***" + key[-2:]
    return f"{key[:3]}***{key[-4:]}"


def resolve_profile(*, cli: str | None, env: dict[str, str], config: Config) -> str:
    name = cli or env.get("SEEDANCE_PROFILE") or config.active
    if name not in config.profiles:
        raise CliError(
            "INVALID_INPUT",
            f"unknown profile {name!r}",
            details={"available": list(config.profiles.keys())},
        )
    return name
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/core/test_config.py -v`
Expected: 10 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/seedance_cli/core/config.py tests/unit/core/test_config.py
git commit -m "feat(core): config schema, atomic chmod-600 save, profile resolver"
```

---

## Task 6: core/media_io.py — local file → base64 payload + role parsing + validation

**Files:**
- Create: `src/seedance_cli/core/media_io.py`
- Create: `tests/unit/core/test_media_io.py`
- Create: `tests/fixtures/tiny.png` (1×1 PNG, ~70 bytes)

- [ ] **Step 1: Generate the PNG fixture**

```bash
python -c "import base64,sys; sys.stdout.buffer.write(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkAAIAAAUAAa4f6OUAAAAASUVORK5CYII='))" > tests/fixtures/tiny.png
```

Local video/audio fixtures aren't needed — every video/audio test uses URLs (mocked via respx in download tests, or no I/O in unit tests).

- [ ] **Step 2: Write the failing tests**

```python
# tests/unit/core/test_media_io.py
import pytest
from pathlib import Path
from seedance_cli.core.media_io import (
    MediaRef, parse_ref, to_payload, MAX_REQUEST_BYTES, RequestBudget,
)
from seedance_cli.framework.errors import CliError


FIXTURES = Path(__file__).parent.parent.parent / "fixtures"


def test_parse_ref_url_no_role():
    ref = parse_ref("https://example.com/a.png", valid_roles={"first_frame", "last_frame", "reference"})
    assert ref.raw == "https://example.com/a.png"
    assert ref.role is None
    assert ref.is_url is True


def test_parse_ref_url_with_port_is_not_split():
    ref = parse_ref("https://host:8080/x.png", valid_roles={"first_frame", "last_frame"})
    assert ref.raw == "https://host:8080/x.png"
    assert ref.role is None


def test_parse_ref_local_with_role():
    ref = parse_ref("./a.png:first_frame", valid_roles={"first_frame", "last_frame"})
    assert ref.raw == "./a.png"
    assert ref.role == "first_frame"
    assert ref.is_url is False


def test_parse_ref_local_role_invalid_means_no_split():
    # ":weird" suffix is NOT a known role → treat the whole thing as path
    ref = parse_ref("./a.png:weird", valid_roles={"first_frame", "last_frame"})
    assert ref.raw == "./a.png:weird"
    assert ref.role is None


def test_to_payload_url_passes_through():
    ref = MediaRef(raw="https://x/y.png", role=None, is_url=True)
    budget = RequestBudget()
    out = to_payload(ref, kind="image", model="2.0", budget=budget)
    assert out["type"] == "image_url"
    assert out["image_url"]["url"] == "https://x/y.png"
    assert "role" not in out
    assert budget.bytes_used == 0


def test_to_payload_local_image_base64():
    ref = MediaRef(raw=str(FIXTURES / "tiny.png"), role="first_frame", is_url=False)
    budget = RequestBudget()
    out = to_payload(ref, kind="image", model="2.0", budget=budget)
    assert out["type"] == "image_url"
    assert out["image_url"]["url"].startswith("data:image/png;base64,")
    assert out["role"] == "first_frame"
    assert budget.bytes_used > 0


def test_to_payload_rejects_unknown_extension(tmp_path: Path):
    bad = tmp_path / "tiny.txt"
    bad.write_text("hi")
    ref = MediaRef(raw=str(bad), role=None, is_url=False)
    with pytest.raises(CliError) as ei:
        to_payload(ref, kind="image", model="2.0", budget=RequestBudget())
    assert ei.value.code == "INVALID_INPUT"


def test_to_payload_rejects_file_too_large(tmp_path: Path):
    big = tmp_path / "big.png"
    big.write_bytes(b"\x89PNG" + b"\x00" * (31 * 1024 * 1024))  # 31 MB
    ref = MediaRef(raw=str(big), role=None, is_url=False)
    with pytest.raises(CliError) as ei:
        to_payload(ref, kind="image", model="2.0", budget=RequestBudget())
    assert ei.value.code == "INVALID_INPUT"
    assert "30" in ei.value.message  # mentions the 30 MB image limit


def test_heic_allowed_on_2_0_only():
    ref_heic = MediaRef(raw="/tmp/x.heic", role=None, is_url=False)
    # We can't easily synthesize a real heic; assert via the format-allowed helper indirectly:
    from seedance_cli.core.media_io import format_allowed
    assert format_allowed("heic", "image", "doubao-seedance-2-0-260128") is True
    assert format_allowed("heic", "image", "doubao-seedance-1-0-pro-250528") is False


def test_request_budget_overflow_raises():
    budget = RequestBudget()
    budget.bytes_used = MAX_REQUEST_BYTES - 100
    with pytest.raises(CliError) as ei:
        budget.add(200)
    assert ei.value.code == "INVALID_INPUT"
    assert "64" in ei.value.message  # mentions 64 MB request body cap
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/unit/core/test_media_io.py -v`
Expected: all FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Write the implementation**

```python
# src/seedance_cli/core/media_io.py
from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from seedance_cli.framework.errors import CliError


MediaKind = Literal["image", "video", "audio"]

MAX_IMAGE_BYTES = 30 * 1024 * 1024
MAX_VIDEO_BYTES = 50 * 1024 * 1024
MAX_AUDIO_BYTES = 15 * 1024 * 1024
MAX_REQUEST_BYTES = 64 * 1024 * 1024

_LIMIT = {"image": MAX_IMAGE_BYTES, "video": MAX_VIDEO_BYTES, "audio": MAX_AUDIO_BYTES}
_LIMIT_LABEL = {"image": "30 MB", "video": "50 MB", "audio": "15 MB"}

IMAGE_EXTS_CORE = {"jpeg", "jpg", "png", "webp", "bmp", "tiff", "gif"}
IMAGE_EXTS_HEIC_MODELS = {
    "doubao-seedance-1-5-pro-251215",
    "doubao-seedance-2-0-260128",
    "doubao-seedance-2-0-fast-260128",
}
VIDEO_EXTS = {"mp4", "mov"}
AUDIO_EXTS = {"wav", "mp3"}

_KIND_TYPE_KEY = {"image": "image_url", "video": "video_url", "audio": "audio_url"}


@dataclass
class MediaRef:
    raw: str
    role: str | None
    is_url: bool


@dataclass
class RequestBudget:
    bytes_used: int = 0

    def add(self, n: int) -> None:
        if self.bytes_used + n > MAX_REQUEST_BYTES:
            raise CliError(
                "INVALID_INPUT",
                f"request body would exceed 64 MB cap "
                f"({(self.bytes_used + n) / 1024 / 1024:.1f} MB). "
                f"upload large media to a public URL (TOS/OSS) and pass the URL instead.",
            )
        self.bytes_used += n


def parse_ref(arg: str, *, valid_roles: set[str]) -> MediaRef:
    is_url = arg.startswith("http://") or arg.startswith("https://")
    if ":" in arg:
        head, _, tail = arg.rpartition(":")
        if tail in valid_roles and head:
            return MediaRef(raw=head, role=tail, is_url=is_url or head.startswith(("http://", "https://")))
    return MediaRef(raw=arg, role=None, is_url=is_url)


def format_allowed(ext: str, kind: MediaKind, model_full_id: str) -> bool:
    ext = ext.lower()
    if kind == "image":
        if ext in IMAGE_EXTS_CORE:
            return True
        if ext in {"heic", "heif"} and model_full_id in IMAGE_EXTS_HEIC_MODELS:
            return True
        return False
    if kind == "video":
        return ext in VIDEO_EXTS
    return ext in AUDIO_EXTS


def _ext_of(path: Path) -> str:
    return path.suffix.lstrip(".").lower()


def _mime_for(ext: str, kind: MediaKind) -> str:
    if kind == "image":
        mapping = {"jpg": "image/jpeg"}
        return mapping.get(ext, f"image/{ext}")
    if kind == "video":
        return "video/mp4" if ext == "mp4" else "video/quicktime"
    return "audio/wav" if ext == "wav" else "audio/mpeg"


def to_payload(ref: MediaRef, *, kind: MediaKind, model: str, budget: RequestBudget) -> dict[str, Any]:
    type_key = _KIND_TYPE_KEY[kind]
    out: dict[str, Any] = {"type": type_key}

    if ref.is_url:
        out[type_key] = {"url": ref.raw}
    else:
        path = Path(ref.raw).expanduser()
        if not path.is_file():
            raise CliError("IO_ERROR", f"file not found: {ref.raw}")
        ext = _ext_of(path)
        if not format_allowed(ext, kind, model):
            raise CliError(
                "INVALID_INPUT",
                f"unsupported {kind} format .{ext} for model {model}",
                details={"path": str(path), "ext": ext, "kind": kind, "model": model},
            )
        size = path.stat().st_size
        if size > _LIMIT[kind]:
            raise CliError(
                "INVALID_INPUT",
                f"{kind} file {path.name} is {size / 1024 / 1024:.1f} MB; limit is {_LIMIT_LABEL[kind]}",
                details={"path": str(path), "size_bytes": size, "limit_bytes": _LIMIT[kind]},
            )
        data = path.read_bytes()
        # base64 expands ~4/3
        budget.add(int(len(data) * 4 / 3) + 100)
        b64 = base64.b64encode(data).decode("ascii")
        out[type_key] = {"url": f"data:{_mime_for(ext, kind)};base64,{b64}"}

    if ref.role:
        out["role"] = ref.role
    return out
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/core/test_media_io.py -v`
Expected: 10 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/seedance_cli/core/media_io.py tests/unit/core/test_media_io.py tests/fixtures/
git commit -m "feat(core): media_io — local→base64, role parsing, size/format validation"
```

> **Implementation-time note (per spec §8):** the `data:<mime>;base64,...` shape stuffed into `image_url.url` is the assumed Volcengine field. Before integration testing against real Ark, read `volcenginesdkarkruntime` SDK source to confirm — if it expects `image_url.b64_json` or a separate field, change `to_payload`'s output shape only (keep tests green by updating expectations).

---

## Task 7: core/content.py — build_content scenario detection + model × param matrix

**Files:**
- Create: `src/seedance_cli/core/content.py`
- Create: `tests/unit/core/test_content.py`

This is the largest pure module — covers 6 scenarios × validation matrix.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/core/test_content.py
import pytest
from seedance_cli.core.content import build_content, build_request, RequestParams
from seedance_cli.core.media_io import MediaRef, RequestBudget
from seedance_cli.framework.errors import CliError


def _img(raw: str, role: str | None = None) -> MediaRef:
    return MediaRef(raw=raw, role=role, is_url=raw.startswith("http"))


def _vid(raw: str, role: str | None = None) -> MediaRef:
    return MediaRef(raw=raw, role=role, is_url=raw.startswith("http"))


def _aud(raw: str) -> MediaRef:
    return MediaRef(raw=raw, role=None, is_url=raw.startswith("http"))


MODEL_2_0 = "doubao-seedance-2-0-260128"
MODEL_2_0_FAST = "doubao-seedance-2-0-fast-260128"
MODEL_1_5_PRO = "doubao-seedance-1-5-pro-251215"
MODEL_1_0_PRO = "doubao-seedance-1-0-pro-250528"


# ---- scenarios ----

def test_text_to_video():
    out = build_content(text="a cat", images=[], videos=[], audios=[], model=MODEL_2_0, budget=RequestBudget())
    assert len(out) == 1 and out[0]["type"] == "text" and out[0]["text"] == "a cat"


def test_image_to_video_first_frame_implicit():
    refs = [_img("https://x/a.png")]
    out = build_content(text="a", images=refs, videos=[], audios=[], model=MODEL_2_0, budget=RequestBudget())
    types = [c["type"] for c in out]
    assert types == ["text", "image_url"]
    assert "role" not in out[1]


def test_first_last_frame_pair():
    refs = [_img("https://x/a.png", role="first_frame"), _img("https://x/b.png", role="last_frame")]
    out = build_content(text="a", images=refs, videos=[], audios=[], model=MODEL_2_0, budget=RequestBudget())
    assert out[1]["role"] == "first_frame"
    assert out[2]["role"] == "last_frame"


def test_multimodal_reference_2_0():
    refs = [_img(f"https://x/{i}.png") for i in range(5)]
    out = build_content(text="a", images=refs, videos=[], audios=[], model=MODEL_2_0, budget=RequestBudget())
    assert sum(1 for c in out if c["type"] == "image_url") == 5


def test_video_edit_2_0():
    out = build_content(text="repaint blue", images=[], videos=[_vid("https://x/v.mp4")], audios=[], model=MODEL_2_0, budget=RequestBudget())
    types = [c["type"] for c in out]
    assert types == ["text", "video_url"]


def test_combo_image_video_audio_2_0():
    out = build_content(
        text="combo",
        images=[_img("https://x/a.png")],
        videos=[_vid("https://x/v.mp4")],
        audios=[_aud("https://x/s.mp3")],
        model=MODEL_2_0,
        budget=RequestBudget(),
    )
    types = [c["type"] for c in out]
    assert types == ["text", "image_url", "video_url", "audio_url"]


# ---- count limits ----

def test_too_many_images_for_multimodal_ref():
    refs = [_img(f"https://x/{i}.png") for i in range(10)]
    with pytest.raises(CliError) as ei:
        build_content(text="a", images=refs, videos=[], audios=[], model=MODEL_2_0, budget=RequestBudget())
    assert ei.value.code == "INVALID_INPUT"


def test_multimodal_ref_requires_2_0_series():
    refs = [_img(f"https://x/{i}.png") for i in range(3)]
    with pytest.raises(CliError) as ei:
        build_content(text="a", images=refs, videos=[], audios=[], model=MODEL_1_5_PRO, budget=RequestBudget())
    assert "multimodal" in ei.value.message.lower() or "2.0" in ei.value.message


def test_first_last_pair_only_first_role_rejected():
    refs = [_img("https://x/a.png", role="first_frame"), _img("https://x/b.png")]
    with pytest.raises(CliError) as ei:
        build_content(text="a", images=refs, videos=[], audios=[], model=MODEL_2_0, budget=RequestBudget())
    assert ei.value.code == "INVALID_INPUT"


def test_text_optional_when_image_present():
    # No prompt but with image: allowed
    out = build_content(text=None, images=[_img("https://x/a.png")], videos=[], audios=[], model=MODEL_2_0, budget=RequestBudget())
    assert all(c["type"] != "text" for c in out)


def test_empty_request_rejected():
    with pytest.raises(CliError) as ei:
        build_content(text=None, images=[], videos=[], audios=[], model=MODEL_2_0, budget=RequestBudget())
    assert ei.value.code == "INVALID_INPUT"


def test_too_many_videos():
    refs = [_vid(f"https://x/{i}.mp4") for i in range(4)]
    with pytest.raises(CliError) as ei:
        build_content(text="a", images=[], videos=refs, audios=[], model=MODEL_2_0, budget=RequestBudget())
    assert ei.value.code == "INVALID_INPUT"


def test_too_many_audios():
    refs = [_aud(f"https://x/{i}.mp3") for i in range(4)]
    with pytest.raises(CliError) as ei:
        build_content(text="a", images=[], videos=[], audios=refs, model=MODEL_2_0, budget=RequestBudget())
    assert ei.value.code == "INVALID_INPUT"


# ---- build_request: top-level params ----

def test_build_request_minimal():
    params = RequestParams(model="2.0", ratio="16:9", duration=5)
    out = build_request(
        params=params, text="a", images=[], videos=[], audios=[], budget=RequestBudget(),
    )
    assert out["model"] == MODEL_2_0
    assert out["ratio"] == "16:9"
    assert out["duration"] == 5
    assert "watermark" in out  # default false
    assert out["watermark"] is False


def test_build_request_generate_audio_requires_supported_model():
    params = RequestParams(model="1.0-pro", generate_audio=True)
    with pytest.raises(CliError) as ei:
        build_request(params=params, text="a", images=[], videos=[], audios=[], budget=RequestBudget())
    assert "generate_audio" in ei.value.message or "generate-audio" in ei.value.message


def test_build_request_frames_only_on_1_0_pro():
    params = RequestParams(model="2.0", frames=29)
    with pytest.raises(CliError) as ei:
        build_request(params=params, text="a", images=[], videos=[], audios=[], budget=RequestBudget())
    assert "frames" in ei.value.message


def test_build_request_frames_grid_check():
    params = RequestParams(model="1.0-pro", frames=30)  # 30 != 25 + 4n
    with pytest.raises(CliError) as ei:
        build_request(params=params, text="a", images=[], videos=[], audios=[], budget=RequestBudget())
    assert "frames" in ei.value.message


def test_build_request_duration_and_frames_mutually_exclusive():
    params = RequestParams(model="1.0-pro", duration=5, frames=29)
    with pytest.raises(CliError) as ei:
        build_request(params=params, text="a", images=[], videos=[], audios=[], budget=RequestBudget())
    assert "duration" in ei.value.message and "frames" in ei.value.message


def test_build_request_flex_rejected_on_2_0():
    params = RequestParams(model="2.0", service_tier="flex")
    with pytest.raises(CliError) as ei:
        build_request(params=params, text="a", images=[], videos=[], audios=[], budget=RequestBudget())
    assert "flex" in ei.value.message.lower() or "service" in ei.value.message.lower()


def test_build_request_1080p_rejected_on_2_0_fast():
    params = RequestParams(model="2.0-fast", resolution="1080p")
    with pytest.raises(CliError) as ei:
        build_request(params=params, text="a", images=[], videos=[], audios=[], budget=RequestBudget())
    assert "1080p" in ei.value.message


def test_build_request_duration_range_per_model():
    # 2.0: 4-15
    with pytest.raises(CliError):
        build_request(params=RequestParams(model="2.0", duration=3), text="a", images=[], videos=[], audios=[], budget=RequestBudget())
    # 1.0-pro: 2-12
    out = build_request(params=RequestParams(model="1.0-pro", duration=2), text="a", images=[], videos=[], audios=[], budget=RequestBudget())
    assert out["duration"] == 2


def test_build_request_camera_fixed_only_on_supported_models():
    with pytest.raises(CliError) as ei:
        build_request(params=RequestParams(model="2.0", camera_fixed=True), text="a", images=[], videos=[], audios=[], budget=RequestBudget())
    assert "camera" in ei.value.message.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/core/test_content.py -v`
Expected: all FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

```python
# src/seedance_cli/core/content.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from seedance_cli.core.client import expand_model
from seedance_cli.core.media_io import MediaRef, RequestBudget, to_payload
from seedance_cli.framework.errors import CliError


_2_0_SERIES = {"doubao-seedance-2-0-260128", "doubao-seedance-2-0-fast-260128"}
_AUDIO_CAPABLE = _2_0_SERIES | {"doubao-seedance-1-5-pro-251215"}
_FLEX_CAPABLE = {
    "doubao-seedance-1-5-pro-251215",
    "doubao-seedance-1-0-pro-250528",
    "doubao-seedance-1-0-pro-fast-251015",
}
_FRAMES_CAPABLE = {"doubao-seedance-1-0-pro-250528", "doubao-seedance-1-0-pro-fast-251015"}
_CAMERA_FIXED_CAPABLE = {
    "doubao-seedance-1-5-pro-251215",
    "doubao-seedance-1-0-pro-250528",
    "doubao-seedance-1-0-pro-fast-251015",
}
_DURATION_RANGE = {
    "doubao-seedance-2-0-260128":          (4, 15),
    "doubao-seedance-2-0-fast-260128":     (4, 15),
    "doubao-seedance-1-5-pro-251215":      (4, 12),
    "doubao-seedance-1-0-pro-250528":      (2, 12),
    "doubao-seedance-1-0-pro-fast-251015": (2, 12),
}

VALID_IMAGE_ROLES = {"first_frame", "last_frame", "reference"}
VALID_VIDEO_ROLES = {"reference"}


@dataclass
class RequestParams:
    model: str
    ratio: str | None = None
    resolution: str | None = None
    duration: int | None = None
    frames: int | None = None
    seed: int | None = None
    camera_fixed: bool | None = None
    watermark: bool = False
    generate_audio: bool | None = None
    return_last_frame: bool = False
    service_tier: Literal["default", "flex"] | None = None
    execution_expires_after: int | None = None
    callback_url: str | None = None


def _detect_scenario(images: list[MediaRef], videos: list[MediaRef], audios: list[MediaRef], model: str) -> str:
    """Decide which validation rules apply and label for errors."""
    n_img = len(images)
    n_vid = len(videos)
    if n_vid > 0:
        return "video_edit_extend"
    if n_img == 0:
        return "text_to_video"
    # has images, no video
    roles = {i.role for i in images}
    if roles & {"first_frame", "last_frame"}:
        return "first_last_frame"
    if n_img == 1:
        return "image_to_video_first"
    return "multimodal_reference"


def build_content(
    *,
    text: str | None,
    images: list[MediaRef],
    videos: list[MediaRef],
    audios: list[MediaRef],
    model: str,
    budget: RequestBudget,
) -> list[dict[str, Any]]:
    full = expand_model(model)

    if text is None and not images and not videos and not audios:
        raise CliError("INVALID_INPUT", "no content: pass -p TEXT or at least one --image/--video/--audio")

    if len(videos) > 3:
        raise CliError("INVALID_INPUT", f"too many videos ({len(videos)}); max 3")
    if len(audios) > 3:
        raise CliError("INVALID_INPUT", f"too many audios ({len(audios)}); max 3")

    scenario = _detect_scenario(images, videos, audios, full)

    if scenario == "first_last_frame":
        if len(images) != 2:
            raise CliError("INVALID_INPUT", "first/last-frame scenario requires exactly 2 images")
        roles = sorted(i.role or "" for i in images)
        if roles != ["first_frame", "last_frame"]:
            raise CliError(
                "INVALID_INPUT",
                "first/last-frame scenario requires one image with :first_frame and one with :last_frame",
            )

    if scenario == "multimodal_reference":
        if full not in _2_0_SERIES:
            raise CliError(
                "INVALID_INPUT",
                f"multimodal reference (multiple images, no role) requires seedance 2.0 series; got {model}",
                details={"model": full},
            )
        if not (1 <= len(images) <= 9):
            raise CliError("INVALID_INPUT", f"multimodal reference allows 1–9 images, got {len(images)}")

    if (videos or audios) and full not in _2_0_SERIES:
        raise CliError(
            "INVALID_INPUT",
            f"video/audio input requires seedance 2.0 series; got {model}",
        )

    content: list[dict[str, Any]] = []
    if text:
        content.append({"type": "text", "text": text})
    for ref in images:
        if ref.role and ref.role not in VALID_IMAGE_ROLES:
            raise CliError("INVALID_INPUT", f"invalid image role {ref.role!r}")
        content.append(to_payload(ref, kind="image", model=full, budget=budget))
    for ref in videos:
        if ref.role and ref.role not in VALID_VIDEO_ROLES:
            raise CliError("INVALID_INPUT", f"invalid video role {ref.role!r}")
        content.append(to_payload(ref, kind="video", model=full, budget=budget))
    for ref in audios:
        content.append(to_payload(ref, kind="audio", model=full, budget=budget))
    return content


def build_request(
    *,
    params: RequestParams,
    text: str | None,
    images: list[MediaRef],
    videos: list[MediaRef],
    audios: list[MediaRef],
    budget: RequestBudget,
) -> dict[str, Any]:
    full = expand_model(params.model)

    if params.duration is not None and params.frames is not None:
        raise CliError("INVALID_INPUT", "--duration and --frames are mutually exclusive")

    if params.frames is not None:
        if full not in _FRAMES_CAPABLE:
            raise CliError("INVALID_INPUT", f"--frames only supported on 1.0-pro / 1.0-pro-fast; got {params.model}")
        f = params.frames
        if not (29 <= f <= 289 and (f - 25) % 4 == 0):
            raise CliError("INVALID_INPUT", f"--frames must satisfy 25 + 4n with n>=1, in [29, 289]; got {f}")

    if params.duration is not None:
        lo, hi = _DURATION_RANGE[full]
        if not (lo <= params.duration <= hi):
            raise CliError("INVALID_INPUT", f"--duration must be in [{lo},{hi}] for {params.model}; got {params.duration}")

    if params.generate_audio is not None and full not in _AUDIO_CAPABLE:
        raise CliError("INVALID_INPUT", f"--generate-audio not supported on {params.model}")

    if params.camera_fixed is not None and full not in _CAMERA_FIXED_CAPABLE:
        raise CliError("INVALID_INPUT", f"--camera-fixed not supported on {params.model}")

    if params.service_tier == "flex" and full not in _FLEX_CAPABLE:
        raise CliError("INVALID_INPUT", f"--service-tier flex not supported on {params.model} (2.0 series excluded)")

    if params.resolution == "1080p" and full == "doubao-seedance-2-0-fast-260128":
        raise CliError("INVALID_INPUT", "--resolution 1080p not supported on 2.0-fast")

    content = build_content(
        text=text, images=images, videos=videos, audios=audios, model=params.model, budget=budget,
    )
    req: dict[str, Any] = {"model": full, "content": content, "watermark": params.watermark}
    for src, key in [
        (params.ratio, "ratio"),
        (params.resolution, "resolution"),
        (params.duration, "duration"),
        (params.frames, "frames"),
        (params.seed, "seed"),
        (params.camera_fixed, "camera_fixed"),
        (params.generate_audio, "generate_audio"),
        (params.service_tier, "service_tier"),
        (params.execution_expires_after, "execution_expires_after"),
        (params.callback_url, "callback_url"),
    ]:
        if src is not None:
            req[key] = src
    if params.return_last_frame:
        req["return_last_frame"] = True
    return req
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/core/test_content.py -v`
Expected: 20 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/seedance_cli/core/content.py tests/unit/core/test_content.py
git commit -m "feat(core): content folding + model×param validation matrix"
```

---

## Task 8: core/naming.py — output path resolution per spec §2.2

**Files:**
- Create: `src/seedance_cli/core/naming.py`
- Create: `tests/unit/core/test_naming.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/core/test_naming.py
import pytest
from pathlib import Path
from seedance_cli.core.naming import resolve_out_path
from seedance_cli.framework.errors import CliError


def test_no_out_lands_in_cwd(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = resolve_out_path(out=None, task_id="cgt-abcdef123", created_at=1700000000, ext="mp4")
    assert p.parent == tmp_path
    assert p.name.endswith(".mp4")
    assert "1700000000" in p.name
    assert "abcdef" in p.name  # short id segment


def test_explicit_file_path(tmp_path: Path):
    target = tmp_path / "my.mp4"
    p = resolve_out_path(out=str(target), task_id="cgt-1", created_at=0, ext="mp4")
    assert p == target


def test_explicit_file_missing_parent_raises(tmp_path: Path):
    target = tmp_path / "missing-subdir" / "my.mp4"
    with pytest.raises(CliError) as ei:
        resolve_out_path(out=str(target), task_id="cgt-1", created_at=0, ext="mp4")
    assert ei.value.code == "IO_ERROR"


def test_directory_with_trailing_slash_auto_creates(tmp_path: Path):
    d = tmp_path / "new" / "sub"
    p = resolve_out_path(out=str(d) + "/", task_id="cgt-xyz789", created_at=1700000000, ext="mp4")
    assert p.parent == d
    assert d.is_dir()
    assert p.name.endswith(".mp4")


def test_extension_swap_for_last_frame(tmp_path: Path):
    p = resolve_out_path(out=None, task_id="cgt-1", created_at=0, ext="png")
    assert p.suffix == ".png"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/core/test_naming.py -v`
Expected: all FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

```python
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
        d = Path(out.rstrip("/" + os.sep))
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/core/test_naming.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/seedance_cli/core/naming.py tests/unit/core/test_naming.py
git commit -m "feat(core): output path resolver (auto-name / dir-mkdir / explicit-file)"
```

---

## Task 9: core/polling.py — task state machine + sigint

**Files:**
- Create: `src/seedance_cli/core/polling.py`
- Create: `tests/unit/core/test_polling.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/core/test_polling.py
import pytest
from types import SimpleNamespace
from seedance_cli.core.polling import poll_until_done, PollResult
from seedance_cli.framework.errors import CliError


class FakeTasksAPI:
    def __init__(self, scripted: list[SimpleNamespace]):
        self._scripted = scripted
        self.calls = 0

    def get(self, task_id: str) -> SimpleNamespace:
        self.calls += 1
        return self._scripted[min(self.calls - 1, len(self._scripted) - 1)]


def _resp(status: str, **extra) -> SimpleNamespace:
    return SimpleNamespace(id="cgt-1", status=status, **extra)


def test_poll_succeeds_after_a_few_running():
    api = FakeTasksAPI([
        _resp("queued"), _resp("running"), _resp("running"),
        _resp("succeeded", content=SimpleNamespace(video_url="https://x")),
    ])
    out = poll_until_done(api, task_id="cgt-1", interval=0.0)
    assert out.status == "succeeded"
    assert out.poll_count == 4
    assert out.elapsed_seconds >= 0


def test_poll_failed_raises_task_failed():
    api = FakeTasksAPI([_resp("running"), _resp("failed", error=SimpleNamespace(code="X", message="bad"))])
    with pytest.raises(CliError) as ei:
        poll_until_done(api, task_id="cgt-1", interval=0.0)
    assert ei.value.code == "TASK_FAILED"
    assert "bad" in (ei.value.details or {}).get("error", {}).get("message", "")


def test_poll_expired_raises_task_expired():
    api = FakeTasksAPI([_resp("expired")])
    with pytest.raises(CliError) as ei:
        poll_until_done(api, task_id="cgt-1", interval=0.0)
    assert ei.value.code == "TASK_EXPIRED"


def test_poll_timeout_raises():
    api = FakeTasksAPI([_resp("running")])
    with pytest.raises(CliError) as ei:
        poll_until_done(api, task_id="cgt-1", interval=0.0, timeout=0.0)
    assert ei.value.code == "POLL_TIMEOUT"
    assert (ei.value.details or {}).get("task_id") == "cgt-1"


def test_poll_emits_progress_callback():
    api = FakeTasksAPI([_resp("queued"), _resp("running"), _resp("succeeded")])
    events = []
    poll_until_done(api, task_id="cgt-1", interval=0.0, on_status=lambda s, n: events.append((s, n)))
    assert events == [("queued", 1), ("running", 2), ("succeeded", 3)]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/core/test_polling.py -v`
Expected: all FAIL.

- [ ] **Step 3: Write the implementation**

```python
# src/seedance_cli/core/polling.py
from __future__ import annotations

import signal
import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol

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
    # SDK may give dataclass-like objects with __dict__ or pydantic-style .model_dump()
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
                    status=status, response=resp,
                    poll_count=poll_count, elapsed_seconds=time.monotonic() - start,
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
                    "TASK_EXPIRED", f"task {task_id} expired",
                    details={"task_id": task_id},
                )
            elapsed = time.monotonic() - start
            if timeout is not None and elapsed >= timeout:
                raise CliError(
                    "POLL_TIMEOUT",
                    f"timeout after {elapsed:.0f}s; task still {status}",
                    details={"task_id": task_id, "last_status": status, "elapsed_seconds": elapsed},
                )
            if interval > 0:
                time.sleep(interval)
    finally:
        signal.signal(signal.SIGINT, prev)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/core/test_polling.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/seedance_cli/core/polling.py tests/unit/core/test_polling.py
git commit -m "feat(core): polling state machine + sigint → POLL_CANCELLED"
```

---

## Task 10: core/download.py — httpx streaming download with respx test

**Files:**
- Create: `src/seedance_cli/core/download.py`
- Create: `tests/unit/core/test_download.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/core/test_download.py
import httpx
import pytest
import respx
from pathlib import Path
from seedance_cli.core.download import download
from seedance_cli.framework.errors import CliError


@respx.mock
def test_download_success(tmp_path: Path):
    respx.get("https://x/y.mp4").mock(return_value=httpx.Response(200, content=b"\x00\x01\x02"))
    out = tmp_path / "out.mp4"
    p = download(url="https://x/y.mp4", out=out)
    assert p == out
    assert out.read_bytes() == b"\x00\x01\x02"


@respx.mock
def test_download_404_raises_io_error(tmp_path: Path):
    respx.get("https://x/y.mp4").mock(return_value=httpx.Response(404))
    with pytest.raises(CliError) as ei:
        download(url="https://x/y.mp4", out=tmp_path / "out.mp4")
    assert ei.value.code == "IO_ERROR"


@respx.mock
def test_download_emits_progress(tmp_path: Path):
    respx.get("https://x/y.mp4").mock(
        return_value=httpx.Response(200, headers={"Content-Length": "10"}, content=b"0123456789"),
    )
    events: list[tuple[int, int | None]] = []
    download(url="https://x/y.mp4", out=tmp_path / "out.mp4",
             on_progress=lambda done, total: events.append((done, total)))
    assert events  # at least one progress event
    assert events[-1][0] == 10
    assert events[-1][1] == 10
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/core/test_download.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the implementation**

```python
# src/seedance_cli/core/download.py
from __future__ import annotations

from pathlib import Path
from typing import Callable

import httpx

from seedance_cli.framework.errors import CliError


def download(
    *,
    url: str,
    out: Path,
    on_progress: Callable[[int, int | None], None] | None = None,
    chunk: int = 64 * 1024,
    timeout: float = 60.0,
) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(out.suffix + ".part")
    try:
        with httpx.stream("GET", url, timeout=timeout, follow_redirects=True) as r:
            if r.status_code != 200:
                raise CliError(
                    "IO_ERROR",
                    f"download failed: HTTP {r.status_code} for {url}",
                    details={"status": r.status_code, "url": url},
                )
            total_hdr = r.headers.get("Content-Length")
            total = int(total_hdr) if total_hdr and total_hdr.isdigit() else None
            done = 0
            with open(tmp, "wb") as f:
                for data in r.iter_bytes(chunk_size=chunk):
                    f.write(data)
                    done += len(data)
                    if on_progress:
                        on_progress(done, total)
    except httpx.HTTPError as e:
        if tmp.exists():
            tmp.unlink()
        raise CliError("NETWORK_ERROR", f"download failed: {e}") from e
    tmp.replace(out)
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/core/test_download.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/seedance_cli/core/download.py tests/unit/core/test_download.py
git commit -m "feat(core): streaming download via httpx with progress callback"
```

---

## Task 11: tests/conftest.py — FakeArk + tmp config dir fixtures

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Write conftest.py**

```python
# tests/conftest.py
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


@dataclass
class FakeTasks:
    created: list[dict[str, Any]] = field(default_factory=list)
    scripted_statuses: list[str] = field(default_factory=lambda: ["succeeded"])
    next_task_id: str = "cgt-2026-fake000001"
    response_extras: dict[str, Any] = field(default_factory=dict)
    list_response: list[Any] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    _status_idx: int = 0

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.created.append(kwargs)
        return SimpleNamespace(id=self.next_task_id)

    def get(self, task_id: str) -> SimpleNamespace:
        status = self.scripted_statuses[min(self._status_idx, len(self.scripted_statuses) - 1)]
        self._status_idx += 1
        extras = dict(self.response_extras)
        if status == "succeeded":
            extras.setdefault("content", SimpleNamespace(
                video_url=extras.pop("video_url", "https://fake/v.mp4"),
                last_frame_url=extras.pop("last_frame_url", None),
            ))
        return SimpleNamespace(
            id=task_id, status=status,
            model="doubao-seedance-2-0-260128",
            created_at=1700000000, updated_at=1700000084,
            seed=42, ratio="16:9", resolution="720p",
            duration=5, framespersecond=24, service_tier="default",
            usage=SimpleNamespace(completion_tokens=1, total_tokens=1),
            **extras,
        )

    def list(self, **kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(items=self.list_response, next_page_token=None)

    def delete(self, task_id: str) -> None:
        self.deleted.append(task_id)


@dataclass
class FakeContentGeneration:
    tasks: FakeTasks = field(default_factory=FakeTasks)


@dataclass
class FakeArk:
    content_generation: FakeContentGeneration = field(default_factory=FakeContentGeneration)


@pytest.fixture
def fake_ark(monkeypatch: pytest.MonkeyPatch) -> FakeArk:
    fake = FakeArk()
    monkeypatch.setattr(
        "seedance_cli.core.client.make_ark_client",
        lambda *_a, **_k: fake,
    )
    return fake


@pytest.fixture
def tmp_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr("seedance_cli.core.config.DEFAULT_CONFIG_PATH", cfg_path)
    # Also export ARK_API_KEY so the auth resolver doesn't blow up unless a test wants it gone.
    monkeypatch.setenv("ARK_API_KEY", "sk-test-1234567890")
    # And clear any host-leaked profile env
    monkeypatch.delenv("SEEDANCE_PROFILE", raising=False)
    monkeypatch.delenv("SEEDANCE_ENDPOINT", raising=False)
    return cfg_path
```

- [ ] **Step 2: Smoke test — verify pytest picks up the fixtures**

```bash
uv run pytest tests/ -q --collect-only | head -30
```
Expected: collection succeeds, no fixture errors.

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: FakeArk + tmp_config fixtures"
```

---

## Task 12: __main__.py — root command, global flags, emitter, error tail

**Files:**
- Modify: `src/seedance_cli/__main__.py` (replace stub)
- Create: `tests/integration/test_root.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/integration/test_root.py
import json
from click.testing import CliRunner
from seedance_cli.__main__ import root


def test_root_version():
    res = CliRunner().invoke(root, ["--version"])
    assert res.exit_code == 0
    assert "seedance-cli" in res.output


def test_root_help():
    res = CliRunner().invoke(root, ["--help"])
    assert res.exit_code == 0
    assert "generate" in res.output
    assert "task" in res.output
    assert "config" in res.output


def test_unknown_command_exits_nonzero():
    res = CliRunner().invoke(root, ["nope"])
    assert res.exit_code != 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_root.py -v`
Expected: FAIL (root not exported).

- [ ] **Step 3: Write the implementation**

```python
# src/seedance_cli/__main__.py
from __future__ import annotations

import sys
from typing import Any

import click

from seedance_cli.framework.envelope import Envelope, Success, Failure, apply_jq, render
from seedance_cli.framework.errors import CliError, exit_code_for, translate


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
    ctx: click.Context, endpoint: str | None, api_key: str | None, profile: str | None,
    fmt: str, jq_expr: str | None, dry_run: bool, verbose: bool, yes: bool,
) -> None:
    """Volcengine Doubao Seedance video generation CLI."""
    ctx.ensure_object(dict)
    ctx.obj.update({
        "endpoint": endpoint, "api_key": api_key, "profile": profile,
        "format": fmt, "jq": jq_expr, "dry_run": dry_run,
        "verbose": verbose, "yes": yes,
    })


def emit(ctx: click.Context, env: Envelope) -> None:
    g = ctx.obj
    if isinstance(env, Success) and g.get("jq"):
        env = apply_jq(env, g["jq"])
    out = render(env, fmt=g.get("format") or "json")
    click.echo(out)


def _register_commands() -> None:
    # Commands are imported here (and registered via their own decorators) to
    # keep import side effects out of plain module load.
    from seedance_cli.commands import generate as _generate, task as _task, config as _config
    root.add_command(_generate.generate)
    root.add_command(_task.task)
    root.add_command(_config.config)


def main() -> None:
    _register_commands()
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
    except Exception as exc:  # noqa: BLE001 — top-level translator
        cli_err = translate(exc)
        click.echo(render(cli_err.to_envelope(), fmt="json"), err=True)
        if "--verbose" in sys.argv:
            import traceback
            traceback.print_exc(file=sys.stderr)
        sys.exit(exit_code_for(cli_err.code))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_root.py -v`
Expected: 3 PASS. (The commands imports may fail until Task 13/14/15 land — see step 5 for the stubs.)

- [ ] **Step 5: Add empty command stubs so root can import them**

```python
# src/seedance_cli/commands/__init__.py
```

```python
# src/seedance_cli/commands/generate.py
import click

@click.command()
def generate() -> None:
    """Create a video generation task (stub)."""
    raise click.ClickException("generate not implemented yet")
```

```python
# src/seedance_cli/commands/task.py
import click

@click.group()
def task() -> None:
    """Manage video generation tasks (stub)."""
```

```python
# src/seedance_cli/commands/config.py
import click

@click.group()
def config() -> None:
    """Manage profiles (stub)."""
```

Re-run: `uv run pytest tests/integration/test_root.py -v` → 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/seedance_cli/__main__.py src/seedance_cli/commands/ tests/integration/test_root.py
git commit -m "feat(cli): root command, global flags, emitter, error tail"
```

---

## Task 13: commands/config.py — init / add / use / list / show / set / unset

**Files:**
- Modify: `src/seedance_cli/commands/config.py` (replace stub)
- Create: `tests/integration/test_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/integration/test_config.py
import json
from pathlib import Path
from click.testing import CliRunner
from seedance_cli.__main__ import root, _register_commands


def _cli():
    _register_commands()
    return CliRunner()


def test_config_list_empty(tmp_config: Path):
    res = _cli().invoke(root, ["config", "list"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)
    assert data == {"ok": True, "data": {"active": "default", "profiles": ["default"]}}


def test_config_set_and_show(tmp_config: Path):
    r1 = _cli().invoke(root, ["config", "set", "api_key", "sk-abcdef1234567890"])
    assert r1.exit_code == 0
    r2 = _cli().invoke(root, ["config", "show"])
    assert r2.exit_code == 0
    data = json.loads(r2.output)["data"]
    assert data["api_key"] == "sk-***7890"
    assert data["endpoint"].startswith("https://ark.cn-beijing.volces.com")


def test_config_add_and_use(tmp_config: Path):
    r1 = _cli().invoke(root, ["config", "add", "prod", "--yes"], input="sk-prodkey\n\n\n")
    assert r1.exit_code == 0
    r2 = _cli().invoke(root, ["config", "use", "prod"])
    assert r2.exit_code == 0
    r3 = _cli().invoke(root, ["config", "list"])
    listing = json.loads(r3.output)["data"]
    assert listing["active"] == "prod"
    assert "prod" in listing["profiles"]


def test_config_set_unknown_key_rejected(tmp_config: Path):
    res = _cli().invoke(root, ["config", "set", "bogus", "x"])
    assert res.exit_code != 0
    out = res.output or res.stderr or ""
    parsed = json.loads(out)
    assert parsed["error"]["code"] == "INVALID_INPUT"


def test_config_unset_clears_field(tmp_config: Path):
    _cli().invoke(root, ["config", "set", "default_model", "2.0"])
    res = _cli().invoke(root, ["config", "unset", "default_model"])
    assert res.exit_code == 0
    shown = json.loads(_cli().invoke(root, ["config", "show"]).output)["data"]
    assert shown["default_model"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_config.py -v`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```python
# src/seedance_cli/commands/config.py
from __future__ import annotations

import click

from seedance_cli.__main__ import emit
from seedance_cli.core.config import (
    DEFAULT_CONFIG_PATH, DEFAULT_ENDPOINT, Config, Profile, load, mask_api_key, save,
)
from seedance_cli.framework.envelope import Success
from seedance_cli.framework.errors import CliError


VALID_SET_KEYS = {"api_key", "endpoint", "default_model"}


@click.group(name="config")
def config() -> None:
    """Manage profiles in ~/.seedance-cli/config.json."""


def _profile_dict(name: str, p: Profile) -> dict:
    return {
        "name": name,
        "api_key": mask_api_key(p.api_key),
        "endpoint": p.endpoint,
        "default_model": p.default_model,
    }


@config.command("list")
@click.pass_context
def config_list(ctx: click.Context) -> None:
    from seedance_cli.core.config import DEFAULT_CONFIG_PATH as path  # late binding for tmp_config patch
    cfg = load(path)
    emit(ctx, Success(data={"active": cfg.active, "profiles": list(cfg.profiles.keys())}))


@config.command("show")
@click.argument("name", required=False)
@click.pass_context
def config_show(ctx: click.Context, name: str | None) -> None:
    from seedance_cli.core.config import DEFAULT_CONFIG_PATH as path
    cfg = load(path)
    target = name or cfg.active
    if target not in cfg.profiles:
        raise CliError("INVALID_INPUT", f"unknown profile {target!r}")
    emit(ctx, Success(data=_profile_dict(target, cfg.profiles[target])))


@config.command("use")
@click.argument("name")
@click.pass_context
def config_use(ctx: click.Context, name: str) -> None:
    from seedance_cli.core.config import DEFAULT_CONFIG_PATH as path
    cfg = load(path)
    if name not in cfg.profiles:
        raise CliError("INVALID_INPUT", f"unknown profile {name!r}")
    cfg.active = name
    save(cfg, path)
    emit(ctx, Success(data={"active": name}))


@config.command("set")
@click.argument("key")
@click.argument("value")
@click.pass_context
def config_set(ctx: click.Context, key: str, value: str) -> None:
    if key not in VALID_SET_KEYS:
        raise CliError("INVALID_INPUT", f"unknown key {key!r}; valid: {sorted(VALID_SET_KEYS)}")
    from seedance_cli.core.config import DEFAULT_CONFIG_PATH as path
    cfg = load(path)
    p = cfg.profiles[cfg.active]
    setattr(p, key, value)
    save(cfg, path)
    emit(ctx, Success(data=_profile_dict(cfg.active, p)))


@config.command("unset")
@click.argument("key")
@click.pass_context
def config_unset(ctx: click.Context, key: str) -> None:
    if key not in VALID_SET_KEYS:
        raise CliError("INVALID_INPUT", f"unknown key {key!r}")
    from seedance_cli.core.config import DEFAULT_CONFIG_PATH as path
    cfg = load(path)
    p = cfg.profiles[cfg.active]
    setattr(p, key, None if key != "endpoint" else DEFAULT_ENDPOINT)
    save(cfg, path)
    emit(ctx, Success(data=_profile_dict(cfg.active, p)))


@config.command("add")
@click.argument("name")
@click.option("--yes", is_flag=True, default=False)
@click.pass_context
def config_add(ctx: click.Context, name: str, yes: bool) -> None:
    from seedance_cli.core.config import DEFAULT_CONFIG_PATH as path
    cfg = load(path)
    if name in cfg.profiles and not yes:
        raise CliError("INVALID_INPUT", f"profile {name!r} already exists; pass --yes to overwrite")
    api_key = click.prompt("API key", hide_input=True, default="", show_default=False)
    endpoint = click.prompt("Endpoint", default=DEFAULT_ENDPOINT, show_default=True)
    model = click.prompt("Default model", default="", show_default=False)
    cfg.profiles[name] = Profile(
        api_key=api_key or None, endpoint=endpoint, default_model=model or None,
    )
    save(cfg, path)
    emit(ctx, Success(data=_profile_dict(name, cfg.profiles[name])))


@config.command("init")
@click.option("--yes", is_flag=True, default=False)
@click.pass_context
def config_init(ctx: click.Context, yes: bool) -> None:
    from seedance_cli.core.config import DEFAULT_CONFIG_PATH as path
    cfg = load(path)
    if cfg.profiles.get("default") and cfg.profiles["default"].api_key and not yes:
        raise CliError("INVALID_INPUT", "default profile already has api_key; pass --yes to overwrite")
    api_key = click.prompt("API key", hide_input=True)
    endpoint = click.prompt("Endpoint", default=DEFAULT_ENDPOINT, show_default=True)
    model = click.prompt("Default model", default="", show_default=False)
    cfg.profiles["default"] = Profile(
        api_key=api_key, endpoint=endpoint, default_model=model or None,
    )
    cfg.active = "default"
    save(cfg, path)
    emit(ctx, Success(data=_profile_dict("default", cfg.profiles["default"])))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_config.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/seedance_cli/commands/config.py tests/integration/test_config.py
git commit -m "feat(cli): config init/add/use/list/show/set/unset"
```

---

## Task 14: commands/generate.py — skeleton (validate, build, --dry-run, --async)

**Files:**
- Modify: `src/seedance_cli/commands/generate.py` (replace stub)
- Create: `tests/integration/test_generate.py` (initial scope: dry-run, async, validation errors)

- [ ] **Step 1: Write the failing tests**

```python
# tests/integration/test_generate.py
import json
from pathlib import Path
from click.testing import CliRunner

from seedance_cli.__main__ import root, _register_commands


def _cli():
    _register_commands()
    return CliRunner()


def test_dry_run_text_to_video(tmp_config: Path):
    res = _cli().invoke(root, ["--dry-run", "generate", "-p", "a cat", "--ratio", "16:9", "--duration", "5"])
    assert res.exit_code == 0, res.output
    body = json.loads(res.output)["data"]
    assert body["request"]["model"] == "doubao-seedance-2-0-260128"
    assert body["request"]["content"][0]["text"] == "a cat"
    assert body["request"]["ratio"] == "16:9"
    assert body["request"]["duration"] == 5
    assert body["request"]["watermark"] is False


def test_dry_run_first_last_frame(tmp_config: Path):
    res = _cli().invoke(root, [
        "--dry-run", "generate", "-p", "smile",
        "--image", "https://x/a.png:first_frame",
        "--image", "https://x/b.png:last_frame",
        "--ratio", "16:9", "--duration", "5",
    ])
    assert res.exit_code == 0, res.output
    content = json.loads(res.output)["data"]["request"]["content"]
    assert content[1]["role"] == "first_frame"
    assert content[2]["role"] == "last_frame"


def test_async_returns_task_id(tmp_config: Path, fake_ark):
    fake_ark.content_generation.tasks.next_task_id = "cgt-2026-abc"
    res = _cli().invoke(root, ["generate", "-p", "a cat", "--async", "--duration", "5"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)["data"]
    assert data["task_id"] == "cgt-2026-abc"
    assert data["status"] == "queued"


def test_invalid_input_frames_on_2_0(tmp_config: Path):
    res = _cli().invoke(root, ["generate", "-p", "a", "--frames", "29", "--async"])
    assert res.exit_code == 2
    err = json.loads(res.output or res.stderr or "")["error"]
    assert err["code"] == "INVALID_INPUT"
    assert "frames" in err["message"]


def test_no_content_rejected(tmp_config: Path):
    res = _cli().invoke(root, ["generate", "--async"])
    assert res.exit_code == 2
    err = json.loads(res.output or res.stderr or "")["error"]
    assert err["code"] == "INVALID_INPUT"


def test_dry_run_redacts_base64(tmp_config: Path, tmp_path: Path):
    img = tmp_path / "tiny.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    res = _cli().invoke(root, ["--dry-run", "generate", "-p", "a", "--image", str(img), "--duration", "5"])
    assert res.exit_code == 0, res.output
    body_text = res.output
    assert "<base64" in body_text
    assert "AAAAAAAAAAAAAAAAAAAA" not in body_text  # raw payload not leaked
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_generate.py -v`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```python
# src/seedance_cli/commands/generate.py
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import click

from seedance_cli.__main__ import emit
from seedance_cli.core.client import DEFAULT_MODEL, expand_model, make_ark_client, resolve_auth
from seedance_cli.core.config import DEFAULT_CONFIG_PATH, load, resolve_profile
from seedance_cli.core.content import RequestParams, VALID_IMAGE_ROLES, VALID_VIDEO_ROLES, build_request
from seedance_cli.core.media_io import RequestBudget, parse_ref
from seedance_cli.framework.envelope import Success
from seedance_cli.framework.errors import CliError


def _redact_base64(req: dict[str, Any]) -> dict[str, Any]:
    """Replace data: URIs with <base64 NNKB> placeholders for safe stdout printing."""
    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(x) for x in node]
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
@click.option("-m", "--model", default=None, help="model id or alias (2.0, 2.0-fast, 1.5-pro, 1.0-pro, 1.0-pro-fast)")
@click.option("--ratio", default=None)
@click.option("--resolution", default=None, type=click.Choice(["480p", "720p", "1080p"]))
@click.option("--duration", default=None, type=int)
@click.option("--frames", default=None, type=int)
@click.option("--seed", default=None, type=int)
@click.option("--camera-fixed/--no-camera-fixed", "camera_fixed", default=None)
@click.option("--watermark/--no-watermark", default=False)
@click.option("--generate-audio/--no-generate-audio", "generate_audio", default=None)
@click.option("--return-last-frame", "return_last_frame", is_flag=True, default=False)
@click.option("--service-tier", "service_tier", type=click.Choice(["default", "flex"]), default=None)
@click.option("--execution-expires-after", "execution_expires_after", type=int, default=None)
@click.option("--callback-url", "callback_url", default=None)
@click.option("--from-json", "from_json", type=click.Path(exists=True), default=None,
              help="load request body from JSON; other flags still override top-level fields")
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
    images: tuple[str, ...], videos: tuple[str, ...], audios: tuple[str, ...],
    model: str | None, ratio: str | None, resolution: str | None,
    duration: int | None, frames: int | None, seed: int | None,
    camera_fixed: bool | None, watermark: bool, generate_audio: bool | None,
    return_last_frame: bool, service_tier: str | None,
    execution_expires_after: int | None, callback_url: str | None,
    from_json: str | None, out: str | None, out_last_frame: str | None,
    is_async: bool, no_download: bool, poll_interval: float | None, timeout: float | None,
) -> None:
    """Create a video generation task."""
    g = ctx.obj

    image_refs = [parse_ref(a, valid_roles=VALID_IMAGE_ROLES) for a in images]
    video_refs = [parse_ref(a, valid_roles=VALID_VIDEO_ROLES) for a in videos]
    audio_refs = [parse_ref(a, valid_roles=set()) for a in audios]

    cfg = load(DEFAULT_CONFIG_PATH)
    profile_name = resolve_profile(cli=g.get("profile"), env=dict(os.environ), config=cfg)
    profile = cfg.profiles[profile_name]
    chosen_model = model or profile.default_model or DEFAULT_MODEL

    base_request: dict[str, Any] = {}
    if from_json:
        base_request = json.loads(Path(from_json).read_text())

    params = RequestParams(
        model=chosen_model, ratio=ratio, resolution=resolution,
        duration=duration, frames=frames, seed=seed,
        camera_fixed=camera_fixed, watermark=watermark,
        generate_audio=generate_audio, return_last_frame=return_last_frame,
        service_tier=service_tier, execution_expires_after=execution_expires_after,
        callback_url=callback_url,
    )

    budget = RequestBudget()
    built = build_request(
        params=params, text=prompt_text,
        images=image_refs, videos=video_refs, audios=audio_refs,
        budget=budget,
    )
    request_body: dict[str, Any] = {**base_request, **built}

    if g.get("dry_run"):
        emit(ctx, Success(data={"request": _redact_base64(request_body), "would_call": "content_generation.tasks.create"}))
        return

    api_key, endpoint = resolve_auth(
        cli_api_key=g.get("api_key"), cli_endpoint=g.get("endpoint"),
        env=dict(os.environ),
        profile_api_key=profile.api_key, profile_endpoint=profile.endpoint,
    )
    client = make_ark_client(api_key, endpoint)
    created = client.content_generation.tasks.create(**request_body)
    task_id = getattr(created, "id", None)
    if not task_id:
        raise CliError("INTERNAL", "API did not return a task id")

    if is_async:
        emit(ctx, Success(data={
            "task_id": task_id, "status": "queued", "model": expand_model(chosen_model),
        }))
        return

    # Blocking + download — implemented in Task 15.
    from seedance_cli.commands.generate_wait import wait_and_download
    wait_and_download(
        ctx=ctx, client=client, task_id=task_id,
        model_full=expand_model(chosen_model),
        out=out, out_last_frame=out_last_frame,
        no_download=no_download, return_last_frame=return_last_frame,
        poll_interval=poll_interval, timeout=timeout,
        service_tier=service_tier or "default",
    )
```

- [ ] **Step 4: Add a stub for `generate_wait` so dry-run / async tests pass without the wait module**

```python
# src/seedance_cli/commands/generate_wait.py
from __future__ import annotations

from typing import Any

import click


def wait_and_download(**_kwargs: Any) -> None:  # filled in by Task 15
    raise click.ClickException("blocking generate path not implemented yet")
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/integration/test_generate.py -v`
Expected: 6 PASS. (Blocking-path tests come in Task 15.)

- [ ] **Step 6: Commit**

```bash
git add src/seedance_cli/commands/generate.py src/seedance_cli/commands/generate_wait.py tests/integration/test_generate.py
git commit -m "feat(cli): generate skeleton — validate, build, --dry-run, --async"
```

---

## Task 15: generate blocking path — polling + download + envelope

**Files:**
- Modify: `src/seedance_cli/commands/generate_wait.py` (replace stub)
- Modify: `tests/integration/test_generate.py` (add blocking tests)

- [ ] **Step 1: Add the failing tests**

Append to `tests/integration/test_generate.py`:

```python
def test_blocking_download_writes_mp4(tmp_config: Path, tmp_path: Path, fake_ark, monkeypatch):
    import httpx, respx
    fake_ark.content_generation.tasks.scripted_statuses = ["queued", "running", "succeeded"]
    fake_ark.content_generation.tasks.response_extras = {"video_url": "https://fake/v.mp4"}
    out = tmp_path / "girl.mp4"

    with respx.mock:
        respx.get("https://fake/v.mp4").mock(return_value=httpx.Response(200, content=b"\x00mp4"))
        res = _cli().invoke(root, [
            "generate", "-p", "girl", "--duration", "5",
            "--poll-interval", "0", "--out", str(out),
        ])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)["data"]
    assert data["status"] == "succeeded"
    assert data["video_path"] == str(out)
    assert out.read_bytes() == b"\x00mp4"


def test_no_download_omits_video_path(tmp_config: Path, fake_ark):
    fake_ark.content_generation.tasks.scripted_statuses = ["succeeded"]
    res = _cli().invoke(root, [
        "generate", "-p", "a", "--duration", "5", "--no-download",
        "--poll-interval", "0",
    ])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)["data"]
    assert "video_url" in data
    assert "video_path" not in data


def test_task_failed_exits_6(tmp_config: Path, fake_ark):
    from types import SimpleNamespace
    fake_ark.content_generation.tasks.scripted_statuses = ["failed"]
    fake_ark.content_generation.tasks.response_extras = {
        "error": SimpleNamespace(code="ContentPolicy", message="bad prompt"),
    }
    res = _cli().invoke(root, [
        "generate", "-p", "a", "--duration", "5", "--poll-interval", "0",
    ])
    assert res.exit_code == 6, res.output
    err = json.loads(res.output or res.stderr or "")["error"]
    assert err["code"] == "TASK_FAILED"


def test_return_last_frame_downloads_png(tmp_config: Path, tmp_path: Path, fake_ark):
    import httpx, respx
    fake_ark.content_generation.tasks.scripted_statuses = ["succeeded"]
    fake_ark.content_generation.tasks.response_extras = {
        "video_url": "https://fake/v.mp4", "last_frame_url": "https://fake/last.png",
    }
    out = tmp_path / "v.mp4"
    lf = tmp_path / "lf.png"
    with respx.mock:
        respx.get("https://fake/v.mp4").mock(return_value=httpx.Response(200, content=b"VID"))
        respx.get("https://fake/last.png").mock(return_value=httpx.Response(200, content=b"PNG"))
        res = _cli().invoke(root, [
            "generate", "-p", "a", "--duration", "5", "--poll-interval", "0",
            "--return-last-frame", "--out", str(out), "--out-last-frame", str(lf),
        ])
    assert res.exit_code == 0, res.output
    assert lf.read_bytes() == b"PNG"
```

- [ ] **Step 2: Run new tests to verify they fail**

Run: `uv run pytest tests/integration/test_generate.py -v`
Expected: the 4 new tests FAIL with "blocking generate path not implemented yet".

- [ ] **Step 3: Replace `generate_wait.py` with the real implementation**

```python
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


def _to_data(resp: Any) -> dict[str, Any]:
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
    *, ctx: click.Context, client: Any, task_id: str, model_full: str,
    out: str | None, out_last_frame: str | None,
    no_download: bool, return_last_frame: bool,
    poll_interval: float | None, timeout: float | None,
    service_tier: str,
) -> None:
    interval = poll_interval if poll_interval is not None else (60.0 if service_tier == "flex" else 10.0)

    console = Console(file=sys.stderr, force_terminal=False)
    with console.status("[cyan]queued...") as status:
        def on_status(s: str, n: int) -> None:
            status.update(f"[cyan]{s} — poll #{n}")

        result = poll_until_done(
            client.content_generation.tasks,
            task_id=task_id, interval=interval, timeout=timeout, on_status=on_status,
        )

    data = _to_data(result.response)
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
        path = resolve_out_path(out=out_last_frame, task_id=task_id,
                                created_at=int(data.get("created_at") or 0), ext="png")
        download(url=last_frame_url, out=path)
        data["last_frame_path"] = str(path)

    emit(ctx, Success(data=data))
```

- [ ] **Step 4: Run all generate tests to verify they pass**

Run: `uv run pytest tests/integration/test_generate.py -v`
Expected: all 10 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/seedance_cli/commands/generate_wait.py tests/integration/test_generate.py
git commit -m "feat(cli): blocking generate — polling + download + envelope"
```

---

## Task 16: commands/task.py — list / get / delete

**Files:**
- Modify: `src/seedance_cli/commands/task.py` (replace stub)
- Create: `tests/integration/test_task.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/integration/test_task.py
import json
from pathlib import Path
from types import SimpleNamespace
from click.testing import CliRunner

from seedance_cli.__main__ import root, _register_commands


def _cli():
    _register_commands()
    return CliRunner()


def test_task_list_empty(tmp_config: Path, fake_ark):
    res = _cli().invoke(root, ["task", "list"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)["data"]
    assert data["tasks"] == []


def test_task_list_with_items(tmp_config: Path, fake_ark):
    fake_ark.content_generation.tasks.list_response = [
        SimpleNamespace(id="cgt-1", status="succeeded", model="doubao-seedance-2-0-260128"),
        SimpleNamespace(id="cgt-2", status="running",   model="doubao-seedance-2-0-260128"),
    ]
    res = _cli().invoke(root, ["task", "list"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)["data"]
    assert len(data["tasks"]) == 2
    assert {t["task_id"] for t in data["tasks"]} == {"cgt-1", "cgt-2"}


def test_task_get(tmp_config: Path, fake_ark):
    fake_ark.content_generation.tasks.scripted_statuses = ["running"]
    res = _cli().invoke(root, ["task", "get", "cgt-1"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)["data"]
    assert data["task_id"] == "cgt-1"
    assert data["status"] == "running"


def test_task_get_wait_and_download(tmp_config: Path, tmp_path: Path, fake_ark):
    import httpx, respx
    fake_ark.content_generation.tasks.scripted_statuses = ["running", "succeeded"]
    fake_ark.content_generation.tasks.response_extras = {"video_url": "https://fake/v.mp4"}
    out = tmp_path / "v.mp4"
    with respx.mock:
        respx.get("https://fake/v.mp4").mock(return_value=httpx.Response(200, content=b"VID"))
        res = _cli().invoke(root, ["task", "get", "cgt-1", "--wait", "--out", str(out), "--poll-interval", "0"])
    assert res.exit_code == 0, res.output
    assert out.read_bytes() == b"VID"


def test_task_delete(tmp_config: Path, fake_ark):
    res = _cli().invoke(root, ["task", "delete", "cgt-1"])
    assert res.exit_code == 0, res.output
    assert fake_ark.content_generation.tasks.deleted == ["cgt-1"]
    data = json.loads(res.output)["data"]
    assert data == {"task_id": "cgt-1", "deleted": True}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/integration/test_task.py -v`
Expected: FAIL.

- [ ] **Step 3: Write the implementation**

```python
# src/seedance_cli/commands/task.py
from __future__ import annotations

import os
from typing import Any

import click

from seedance_cli.__main__ import emit
from seedance_cli.commands.generate_wait import _to_data, wait_and_download
from seedance_cli.core.client import make_ark_client, resolve_auth
from seedance_cli.core.config import DEFAULT_CONFIG_PATH, load, resolve_profile
from seedance_cli.framework.envelope import Success


def _client(ctx: click.Context):
    cfg = load(DEFAULT_CONFIG_PATH)
    profile_name = resolve_profile(cli=ctx.obj.get("profile"), env=dict(os.environ), config=cfg)
    profile = cfg.profiles[profile_name]
    api_key, endpoint = resolve_auth(
        cli_api_key=ctx.obj.get("api_key"), cli_endpoint=ctx.obj.get("endpoint"),
        env=dict(os.environ),
        profile_api_key=profile.api_key, profile_endpoint=profile.endpoint,
    )
    return make_ark_client(api_key, endpoint)


@click.group(name="task")
def task() -> None:
    """Manage video generation tasks."""


@task.command("list")
@click.option("--status", "statuses", multiple=True,
              type=click.Choice(["queued", "running", "succeeded", "failed", "expired"]))
@click.option("--model", default=None)
@click.option("--page-size", "page_size", type=int, default=None)
@click.option("--page-token", "page_token", default=None)
@click.pass_context
def task_list(ctx: click.Context, statuses: tuple[str, ...], model: str | None,
              page_size: int | None, page_token: str | None) -> None:
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
    emit(ctx, Success(data={
        "tasks": tasks_data,
        "next_page_token": getattr(resp, "next_page_token", None),
    }))


@task.command("get")
@click.argument("task_id")
@click.option("--wait", is_flag=True, default=False)
@click.option("--out", default=None)
@click.option("--poll-interval", "poll_interval", type=float, default=None)
@click.option("--timeout", type=float, default=None)
@click.pass_context
def task_get(ctx: click.Context, task_id: str, wait: bool, out: str | None,
             poll_interval: float | None, timeout: float | None) -> None:
    client = _client(ctx)
    if wait:
        wait_and_download(
            ctx=ctx, client=client, task_id=task_id, model_full="",
            out=out, out_last_frame=None,
            no_download=(out is None), return_last_frame=False,
            poll_interval=poll_interval, timeout=timeout,
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_task.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/seedance_cli/commands/task.py tests/integration/test_task.py
git commit -m "feat(cli): task list / get / get --wait / delete"
```

---

## Task 17: skills/seedance/SKILL.md

**Files:**
- Create: `skills/seedance/SKILL.md`

- [ ] **Step 1: Write the SKILL document**

Save the following to `skills/seedance/SKILL.md`. (Spec §6 is the source of truth; this is the literal text the SKILL ships with.)

```markdown
---
name: seedance
version: 1.0.0
description: "当用户需要生成视频、首帧/首尾帧生视频、多模态参考生视频、编辑/延长视频，或需要连续多段视频接龙时使用。"
metadata:
  requires:
    bins: ["seedance-cli"]
  cliHelp: "seedance-cli --help"
---

# seedance

一句话:本 SKILL 驱动 `seedance-cli`,用 Volcengine Doubao Seedance 系列模型生成 / 编辑 / 延长视频。

**核心原则**:统一走 `seedance-cli` 入口(不手拼 curl);视频生成是异步任务,默认 `seedance-cli generate` 已经做了轮询 + 下载,不要绕开;**Claude 看不见 MP4**,要么验文件存在 + 元数据,要么 ffmpeg 抽帧后 Read 静图。

## 前置

1. 确认 `seedance-cli` 可执行(`which seedance-cli` 或 `seedance-cli --version`)。不可执行则提示用户 `uv tool install seedance-cli` 或 `pipx install seedance-cli`。
2. 配置 API key:优先 env `ARK_API_KEY`;缺失时引导 `seedance-cli config init`。
3. 默认 endpoint 是 `https://ark.cn-beijing.volces.com/api/v3`,自建/代理 endpoint 走 `seedance-cli config set endpoint https://<...>/api/v3` 或 `--endpoint` 单次覆盖。

## 多 profile 配置

```bash
seedance-cli config list                # 列所有 profile,active 标 *
seedance-cli config use <name>          # 切 active
seedance-cli config add <name>          # 向导式新增
seedance-cli --profile <name> generate ...   # 单次覆盖,不改 active
seedance-cli config show [<name>]       # 查看(api_key 已脱敏)
```

优先级:`--profile flag > SEEDANCE_PROFILE env > 文件 active`。`--api-key` / `--endpoint` 是字段级覆盖,不会让 `--profile` 失效。

## 核心命令速查

```bash
# 文生视频
seedance-cli generate -p "<prompt>" --ratio 16:9 --duration 5 --out v.mp4

# 图生视频 - 首帧
seedance-cli generate -p "<prompt>" --image start.png --duration 5 --out v.mp4

# 图生视频 - 首尾帧
seedance-cli generate -p "<prompt>" --image first.png:first_frame --image last.png:last_frame --duration 5 --out v.mp4

# 多模态参考(2.0)
seedance-cli generate -p "<prompt>" --image a.png --image b.png --image c.png --duration 5 --out v.mp4

# 视频编辑 / 延长(2.0)
seedance-cli generate -p "把房子刷成蓝色" --video orig.mp4 --duration 5 --out edited.mp4

# 多模态组合(2.0):图 + 视频 + 音频
seedance-cli generate -p "<prompt>" --image a.png --video b.mp4 --audio bgm.mp3 --out v.mp4

# 任务管理
seedance-cli task list --status running --status queued
seedance-cli task get <task_id> --wait --out path.mp4
seedance-cli task delete <task_id>
```

## 模型选型

| 想要 | 模型 (`-m`) | 关键差异 |
|---|---|---|
| 默认 / 最强 | `2.0`(默认) | 全能力,含多模态参考 / 编辑 / 延长 / 有声 |
| 又快又省 | `2.0-fast` | 同 2.0 但无 1080p |
| 离线推理省钱 | `1.5-pro --service-tier flex` | 2.0 不支持 flex;价格 50% |
| 指定帧数 | `1.0-pro --frames 29` | 唯一支持 `--frames`(满足 25+4n,29-289) |

## 参数选型

| 意图 | 推荐参数 |
|---|---|
| 试拍 / 预览 | `--ratio 16:9 --resolution 720p --duration 5` |
| 横版定稿 | `--ratio 16:9 --resolution 1080p`(2.0-fast 除外) |
| 竖版短视频 | `--ratio 9:16` |
| 跟随首帧自适应宽高比 | `--ratio adaptive` |
| 离线推理 | `-m 1.5-pro --service-tier flex --execution-expires-after 172800` |
| 有声视频 | `--generate-audio`(仅 2.0 / 2.0-fast / 1.5-pro) |
| 拿到尾帧做接龙 | `--return-last-frame --out-last-frame last.png` |

## 本地输入 vs URL

- 本地路径(`./a.png`、`/path/v.mp4`)自动 base64 编码,**注意限额**:单图 ≤ 30 MB、单视频 ≤ 50 MB、单音频 ≤ 15 MB,请求体总 ≤ 64 MB。
- 超限会报 `INVALID_INPUT`,提示先上传到 TOS / OSS 拿到公开 URL,再传 `--image https://...`。
- URL 输入零成本,优先用 URL。

## 连续视频接龙 workflow(本 SKILL 主战场)

**触发**:用户说"做一段连续故事 / 接着上一段 / 接龙生成 / 多段视频"。

**产物目录**
```
story/<topic>/
├── clip-1.mp4
├── clip-2.mp4
├── clip-3.mp4
├── last-frame-1.png
├── last-frame-2.png
└── final.mp4
```

`<topic>` 取自用户对此次任务的简短命名;没给就根据语义自造一个 kebab-case 词,如 `fox-girl-story`。

### Step 1 - 写分镜

让用户先给 N 段提示词。只给一段总意图时,Claude 先拆成 3-5 段分镜并复述给用户确认,**不要直接开生**。

### Step 2 - 首段

```bash
seedance-cli generate -m 2.0 \
  -p "<clip-1 prompt>" \
  [--image start.png:first_frame] \
  --return-last-frame \
  --ratio 16:9 --resolution 720p --duration 5 \
  --out story/<topic>/clip-1.mp4 \
  --out-last-frame story/<topic>/last-frame-1.png
```

读 stdout envelope 拿 `last_frame_path`。**`--ratio` `--resolution` `--duration` 跨段保持不变**,改了会拼接撕裂。

### Step 3 - 续段(循环 i = 2…N)

```bash
seedance-cli generate -m 2.0 \
  -p "<clip-i prompt - 必须完整重述视觉要素>" \
  --image story/<topic>/last-frame-{i-1}.png:first_frame \
  --return-last-frame \
  --ratio 16:9 --resolution 720p --duration 5 \
  --out story/<topic>/clip-{i}.mp4 \
  --out-last-frame story/<topic>/last-frame-{i}.png
```

### Step 4 - 跨段一致性 prompt 模板

照下面 4 段模板**填充**,然后展开成自然语言(去掉 `[...]` 标签):

```
[本段动作]:<这一段主体在做什么>
[延续上段]:<上一段最后的状态 - 主体姿态/场景/光线,必须复述,模型不读上下文>
[配色与风格]:<跨段稳定的视觉调性>
[镜头与节奏]:<本段镜头运动>
```

**不要**写 "like before but..." / "保持上一段不变,只改 X" - 模型没有上下文,它不懂"上一段"。每段 prompt 必须**完整自包含**。

### Step 5 - 拼接

所有段都成功后,给用户一行 ffmpeg:

```bash
ffmpeg -f concat -safe 0 \
  -i <(for f in story/<topic>/clip-*.mp4; do echo "file '$PWD/$f'"; done) \
  -c copy story/<topic>/final.mp4
```

不满意时**只重生有问题的那段 + 后续所有段**(链断了)。

### 必须做

- ✅ 每段 prompt 完整自包含 - 模型不读对话上下文
- ✅ `--ratio` `--resolution` `--duration` 跨段保持
- ✅ 每段成功后告诉用户「clip-i 已落盘,下一段将以本段尾帧续接」

### 必须不做

- ❌ 中间段省 `--return-last-frame` / `--out-last-frame`,链就断了
- ❌ 没拿到尾帧的情况下凭脑补写下一段 prompt
- ❌ 跨段换模型 / 换 seed / 换 ratio
- ❌ 试拍直接 1080p 全开 - 4 段 1080p 慢且贵;先 720p,定稿再 1080p 重出

## 异步与任务管理

什么时候用 `--async`:
- 一次性派多个任务,让队列跑
- 任务很长(1080p + 12s + 2.0),开 `--async` 然后睡一觉
- CI 编排,不想 Python 进程挂半小时

恢复模式:

```bash
seedance-cli task list --status running --status queued    # 看哪些没收
seedance-cli task get <id> --wait --out path.mp4           # 接回阻塞下载
seedance-cli task delete <id>                              # 取消排队 / 删历史
```

`POLL_CANCELLED`(Ctrl-C)或 `POLL_TIMEOUT`(`--timeout` 命中)时,envelope 里仍含 `task_id`,用 `task get --wait` 续杯,**不要从头重发**(会浪费 token)。

## 产物验证

**Claude 看不见 MP4**。能做的:

1. 确认 `video_path` 存在、`os.path.getsize` 非零
2. 报 envelope 里的 `duration` / `resolution` / `ratio` / `framespersecond` 给用户
3. 想"看"内容时,ffmpeg 抽帧 + Read:

```bash
ffmpeg -ss 00:00:00 -i clip.mp4 -frames:v 1 preview-first.jpg
ffmpeg -sseof -1 -i clip.mp4 -frames:v 1 preview-last.jpg
```

然后 `Read preview-first.jpg / preview-last.jpg` 让自己看到首尾帧,给用户描述。没 ffmpeg 就明说"装一下或者你自己看",别假装看到了。

## 常见错误处置

按退出码处理:

- `CONFIG_MISSING` / `INVALID_INPUT`(exit 2)→ 引导 `config init` 或修参数。
- `IO_ERROR`(exit 3)→ 检查 `--out` 路径是否存在 / 可写;父目录不存在时改用结尾带 `/` 的目录形式触发 mkdir。
- `ARK_API_ERROR`(exit 4)→ 读 `details.status` 和 `details.message`:429 退避后重试;400 改 prompt / 参数。
- `NETWORK_ERROR`(exit 5)→ 重试;多次失败核对 `config show` 的 endpoint。
- `TASK_FAILED`(exit 6)→ 看 `details.error`,多半是内容策略或参考图问题(尤其 2.0 不接受真人脸)。
- `TASK_EXPIRED`(exit 7)→ 任务过 24h 被清,重新建。
- `POLL_TIMEOUT` / `POLL_CANCELLED`(exit 8/9)→ envelope 里有 `task_id`,用 `task get --wait` 续。
- `INTERNAL`(exit 10)→ bug,带 `--verbose` 跑一次拿 stacktrace,报 issue。

## Red Flags - 出现这些信号立即停下

- 我正要把 gpt-image"重生成本图"心智搬过来 → 停,seedance 多轮 = **故事接龙**,不是 A/B
- 我正要 `Read clip.mp4` → 停,Read 读不出视频,要么抽帧要么报元数据
- 我正要在没 `--return-last-frame` 的情况下接龙 → 停,链断了模型从零构图
- 我正要默认开 1080p → 停,试拍 720p
- 我正要自己写 Python 轮询循环 → 停,CLI 已经轮询了,用 `--wait` 别绕开
- 我正要把多段任务并发派出去 → 停,接龙必须串行(每段依赖上段尾帧),且并发受模型限制(个人 3 / 企业 10)
- 我正要凭记忆汇报 "已生成" → 停,先确认 `video_path` 存在 + 报元数据

## 不要做

- 不要分析或识别已有视频(本 CLI 不覆盖 vision 任务)
- 不要尝试 model id 之外的能力(联网搜索、样片模式 v1 不支持)
- 不要自己拼 curl 调 Ark - 走 CLI,envelope / 错误路径才统一
- 不要在 prompt 里硬写比例数字而 `--ratio` 是另一个,会拼接撕裂
- 不要把 `ARK_API_KEY` 写进 shell history,用 `config init` 或 env

## 安全与预期

- 单段视频生成耗时 30s - 几分钟;1080p + 长 duration + 2.0 会明显更慢更贵。
- `--service-tier flex` 价格是 default 的 50%,但只支持 1.5-pro / 1.0-pro 系列,且响应时间是小时级。
- 视频文件可能很大,务必传 `--out` 显式路径,不要在任意目录默认落盘。
- 脚本场景首选 `--format json` + `--jq '.data.video_path'`,稳定可解析。
```

- [ ] **Step 2: Commit**

```bash
git add skills/
git commit -m "docs(skill): seedance SKILL.md for Claude Code agents"
```

---

## Task 18: README + CI + release pipeline

**Files:**
- Create: `README.md`
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: Write `README.md`**

```markdown
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
```

- [ ] **Step 2: Write `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ${{ matrix.os }}
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest]
        python: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - name: Pin Python
        run: uv python pin ${{ matrix.python }}
      - name: Install
        run: uv sync --all-extras
      - name: Lint
        run: uv run ruff check . && uv run ruff format --check .
      - name: Typecheck
        run: uv run pyright
      - name: Tests
        run: uv run pytest --cov=seedance_cli --cov-report=xml
      - name: Upload coverage
        if: matrix.os == 'ubuntu-latest' && matrix.python == '3.12'
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
```

- [ ] **Step 3: Write `.github/workflows/release.yml`**

```yaml
name: Release

on:
  push:
    tags: ["v*"]

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      id-token: write     # for PyPI OIDC trusted publishing
      contents: write     # for GitHub Release
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - run: uv sync --all-extras
      - run: uv run ruff check . && uv run ruff format --check .
      - run: uv run pyright
      - run: uv run pytest
      - name: Build
        run: uv build
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
      - name: GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          generate_release_notes: true
          files: dist/*
```

- [ ] **Step 4: Verify CI lint locally before pushing**

Run:
```bash
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest -q
```
Expected: all green. Fix anything ruff/pyright complains about inline.

- [ ] **Step 5: Commit**

```bash
git add README.md .github/
git commit -m "docs+ci: README, GitHub Actions for CI and release"
```

---

## Task 19: Smoke test against real Ark (manual, deferred)

Implementation-time only; not automated. The plan owner runs this once before tagging `v1.0.0`.

- [ ] **Step 1: Verify base64 field shape**

Open `volcengine-python-sdk` source on disk (after `uv sync`):
```bash
uv run python -c "import volcenginesdkarkruntime, inspect; print(inspect.getfile(volcenginesdkarkruntime))"
```
Grep the source tree for `image_url` and `b64_json` to confirm whether `data:<mime>;base64,...` in `image_url.url` is accepted, or if the SDK expects a separate field. If different, update `core/media_io.py::to_payload` and the corresponding test in `test_media_io.py::test_to_payload_local_image_base64`, then re-run the test suite.

- [ ] **Step 2: Verify video / audio content shapes**

Same approach for `video_url` and `audio_url` content items. Adjust `_KIND_TYPE_KEY` in `core/media_io.py` and the scenario assertions in `test_content.py` if the field names differ.

- [ ] **Step 3: Run a real text-to-video task**

```bash
export ARK_API_KEY=<real key>
seedance-cli generate -p "a tabby cat yawning at the camera" --ratio 16:9 --duration 5 --out smoke.mp4
ls -la smoke.mp4
```
Expected: succeeded envelope, MP4 lands on disk. Open it in a player and eyeball the result.

- [ ] **Step 4: Run a real first-last frame task**

Pick two real frames (use any PNG) and run the first-last scenario end-to-end.

- [ ] **Step 5: Verify pagination shape**

```bash
seedance-cli task list --page-size 2
```
If `next_page_token` is not how the SDK paginates, adjust `commands/task.py::task_list`.

- [ ] **Step 6: Tag and release**

```bash
# bump version in pyproject.toml + src/seedance_cli/__main__.py to 1.0.0
git commit -am "chore: bump version to 1.0.0"
git tag v1.0.0
git push origin main --tags
```

GitHub Actions release pipeline builds + publishes to PyPI.

---

## Task 20: Final sweep — coverage, docs, version sync

- [ ] **Step 1: Coverage check**

```bash
uv run pytest --cov=seedance_cli --cov-report=term-missing
```
Target: > 85% line coverage on `core/` and `framework/`. Add tests for any uncovered branches you find.

- [ ] **Step 2: Help text smoke**

```bash
uv run seedance-cli --help
uv run seedance-cli generate --help
uv run seedance-cli task --help
uv run seedance-cli config --help
```
Read each help page; if any flag description is wrong or stale, fix it in the click decorator.

- [ ] **Step 3: Version sync**

Confirm `pyproject.toml::version`, `src/seedance_cli/__main__.py::__version__`, and `skills/seedance/SKILL.md::version` are all the same. Bump together; never independently.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: pre-release sweep — coverage, help text, version sync"
```

---

## Recap of files created

```
seedance-cli/
├── pyproject.toml
├── README.md
├── .github/workflows/ci.yml
├── .github/workflows/release.yml
├── src/seedance_cli/
│   ├── __init__.py
│   ├── __main__.py
│   ├── framework/
│   │   ├── __init__.py
│   │   ├── envelope.py
│   │   └── errors.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── config.py
│   │   ├── content.py
│   │   ├── download.py
│   │   ├── media_io.py
│   │   ├── naming.py
│   │   └── polling.py
│   └── commands/
│       ├── __init__.py
│       ├── config.py
│       ├── generate.py
│       ├── generate_wait.py
│       └── task.py
├── skills/seedance/SKILL.md
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── fixtures/
    │   └── tiny.png
    ├── unit/
    │   ├── __init__.py
    │   ├── framework/{__init__.py,test_envelope.py,test_errors.py}
    │   └── core/{__init__.py,test_client.py,test_config.py,test_content.py,test_download.py,test_media_io.py,test_naming.py,test_polling.py}
    └── integration/
        ├── __init__.py
        ├── test_config.py
        ├── test_generate.py
        ├── test_root.py
        └── test_task.py
```

Total: ~15 source files + ~12 test files. Spec §1 file structure honored exactly except `commands/generate.py` was split into `generate.py` (skeleton) + `generate_wait.py` (blocking path) so each file stays focused — noted in commit history.
