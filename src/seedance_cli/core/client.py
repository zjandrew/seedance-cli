# src/seedance_cli/core/client.py
from __future__ import annotations

from typing import Any, Protocol

from seedance_cli.framework.errors import CliError

DEFAULT_ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL = "doubao-seedance-2-0-260128"

MODEL_ALIASES: dict[str, str] = {
    "2.0": "doubao-seedance-2-0-260128",
    "2.0-fast": "doubao-seedance-2-0-fast-260128",
    "1.5-pro": "doubao-seedance-1-5-pro-251215",
    "1.0-pro": "doubao-seedance-1-0-pro-250528",
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
    # Lazily import the SDK so unit tests that mock this factory don't need the
    # SDK at module load time, and so the top-level CLI startup stays fast.
    from volcenginesdkarkruntime import Ark  # pyright: ignore[reportMissingImports]

    return Ark(api_key=api_key, base_url=endpoint)
