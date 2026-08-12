# src/seedance_cli/core/client.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from seedance_cli.framework.errors import CliError

DEFAULT_ENDPOINT = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL = "doubao-seedance-2-0-260128"

MODEL_ALIASES: dict[str, str] = {
    "2.5": "doubao-seedance-2-5-260628",
    "2.0": "doubao-seedance-2-0-260128",
    "2.0-fast": "doubao-seedance-2-0-fast-260128",
    "2.0-mini": "doubao-seedance-2-0-mini-260615",
    "1.5-pro": "doubao-seedance-1-5-pro-251215",
    "1.0-pro": "doubao-seedance-1-0-pro-250528",
    "1.0-pro-fast": "doubao-seedance-1-0-pro-fast-251015",
}

_FULL_IDS = set(MODEL_ALIASES.values())


@dataclass(frozen=True)
class Capability:
    """Local-validation surface for one model, per ADR-0001: only constraints that
    are explicit in the Ark docs (82379 series) AND expensive to fail server-side
    are enforced locally; everything else passes through."""

    multimodal_reference: bool = False  # multiple reference images
    video_audio_input: bool = False  # video/audio reference inputs
    audio_only_input: bool = False  # audio as the sole reference input
    generate_audio: bool = False
    flex: bool = False  # --service-tier flex
    frames: bool = False
    camera_fixed: bool = False
    seed: bool = True  # default True: only documented prohibitions are gated
    task_type: bool = True  # omni_reference_task_type (2.5+); default passthrough
    output_format: bool = True  # mp4/mov selection (2.5+); default passthrough
    forced_adaptive_ratio: bool = False  # some scenarios force ratio=adaptive (2.5)
    duration_range: tuple[int, int] | None = None  # None = --duration unsupported
    duration_minus_one: bool = False  # duration=-1 lets the model decide
    explicit_reference_roles: bool = False  # reference_* roles mandatory on inputs
    resolutions: frozenset[str] | None = None  # None = no local restriction
    max_ref_images: int = 9
    max_videos: int = 3
    max_audios: int = 3
    heic: bool = False  # heic/heif image inputs


_RES_480_720 = frozenset({"480p", "720p"})
_RES_480_1080 = frozenset({"480p", "720p", "1080p"})
_RES_480_4K = frozenset({"480p", "720p", "1080p", "4k"})

CAPABILITIES: dict[str, Capability] = {
    # 2.5 — docs 82379/2607688 (tutorial) + 1520757 (create API)
    "doubao-seedance-2-5-260628": Capability(
        multimodal_reference=True,
        video_audio_input=True,
        audio_only_input=True,
        generate_audio=True,
        seed=False,
        forced_adaptive_ratio=True,
        duration_range=(4, 30),
        duration_minus_one=True,
        explicit_reference_roles=True,
        resolutions=_RES_480_720,
        max_ref_images=30,
        max_videos=10,
        max_audios=10,
        heic=True,
    ),
    # 2.0 series — docs 82379/2291680
    "doubao-seedance-2-0-260128": Capability(
        multimodal_reference=True,
        video_audio_input=True,
        generate_audio=True,
        seed=False,
        task_type=False,
        output_format=False,
        duration_range=(4, 15),
        duration_minus_one=True,
        resolutions=_RES_480_4K,
        heic=True,
    ),
    "doubao-seedance-2-0-fast-260128": Capability(
        multimodal_reference=True,
        video_audio_input=True,
        generate_audio=True,
        seed=False,
        task_type=False,
        output_format=False,
        duration_range=(4, 15),
        duration_minus_one=True,
        resolutions=_RES_480_720,
        heic=True,
    ),
    "doubao-seedance-2-0-mini-260615": Capability(
        multimodal_reference=True,
        video_audio_input=True,
        generate_audio=True,
        seed=False,
        task_type=False,
        output_format=False,
        duration_range=(4, 15),
        duration_minus_one=True,
        resolutions=_RES_480_720,
        heic=True,
    ),
    # 1.x series — docs 82379/2298881
    "doubao-seedance-1-5-pro-251215": Capability(
        generate_audio=True,
        task_type=False,
        output_format=False,
        flex=True,
        camera_fixed=True,
        duration_range=(4, 12),
        duration_minus_one=True,
        resolutions=_RES_480_1080,
        heic=True,
    ),
    "doubao-seedance-1-0-pro-250528": Capability(
        flex=True,
        task_type=False,
        output_format=False,
        frames=True,
        camera_fixed=True,
        duration_range=(2, 12),
        resolutions=_RES_480_1080,
    ),
    "doubao-seedance-1-0-pro-fast-251015": Capability(
        flex=True,
        task_type=False,
        output_format=False,
        frames=True,
        camera_fixed=True,
        duration_range=(2, 12),
        resolutions=_RES_480_1080,
    ),
}

# Forward-compat models (unrecognized doubao-seedance-* ids) degrade to the
# conservative default: text/single-image only, scalar params passed through.
_UNKNOWN_CAPABILITY = Capability()


def capability_of(full_id: str) -> Capability:
    return CAPABILITIES.get(full_id, _UNKNOWN_CAPABILITY)


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
