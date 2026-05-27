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
_FRAMES_CAPABLE = {
    "doubao-seedance-1-0-pro-250528",
    "doubao-seedance-1-0-pro-fast-251015",
}
_CAMERA_FIXED_CAPABLE = {
    "doubao-seedance-1-5-pro-251215",
    "doubao-seedance-1-0-pro-250528",
    "doubao-seedance-1-0-pro-fast-251015",
}
_DURATION_RANGE = {
    "doubao-seedance-2-0-260128": (4, 15),
    "doubao-seedance-2-0-fast-260128": (4, 15),
    "doubao-seedance-1-5-pro-251215": (4, 12),
    "doubao-seedance-1-0-pro-250528": (2, 12),
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


def _detect_scenario(
    images: list[MediaRef], videos: list[MediaRef], audios: list[MediaRef], model: str
) -> str:
    """Decide which validation rules apply and label for errors."""
    n_img = len(images)
    n_vid = len(videos)
    if n_vid > 0:
        return "video_edit_extend"
    if n_img == 0:
        return "text_to_video"
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
        raise CliError(
            "INVALID_INPUT",
            "no content: pass -p TEXT or at least one --image/--video/--audio",
        )

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
                "first/last-frame scenario requires one image with :first_frame"
                " and one with :last_frame",
            )

    if scenario == "multimodal_reference":
        if full not in _2_0_SERIES:
            raise CliError(
                "INVALID_INPUT",
                f"multimodal reference (multiple images, no role) requires"
                f" seedance 2.0 series; got {model}",
                details={"model": full},
            )
        if not (1 <= len(images) <= 9):
            raise CliError(
                "INVALID_INPUT", f"multimodal reference allows 1-9 images, got {len(images)}"
            )

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
            raise CliError(
                "INVALID_INPUT",
                f"--frames only supported on 1.0-pro / 1.0-pro-fast; got {params.model}",
            )
        f = params.frames
        if not (29 <= f <= 289 and (f - 25) % 4 == 0):
            raise CliError(
                "INVALID_INPUT",
                f"--frames must satisfy 25 + 4n with n>=1, in [29, 289]; got {f}",
            )

    if params.duration is not None:
        lo, hi = _DURATION_RANGE[full]
        if not (lo <= params.duration <= hi):
            raise CliError(
                "INVALID_INPUT",
                f"--duration must be in [{lo},{hi}] for {params.model}; got {params.duration}",
            )

    if params.generate_audio is not None and full not in _AUDIO_CAPABLE:
        raise CliError("INVALID_INPUT", f"--generate-audio not supported on {params.model}")

    if params.camera_fixed is not None and full not in _CAMERA_FIXED_CAPABLE:
        raise CliError("INVALID_INPUT", f"--camera-fixed not supported on {params.model}")

    if params.service_tier == "flex" and full not in _FLEX_CAPABLE:
        raise CliError(
            "INVALID_INPUT",
            f"--service-tier flex not supported on {params.model} (2.0 series excluded)",
        )

    if params.resolution == "1080p" and full == "doubao-seedance-2-0-fast-260128":
        raise CliError("INVALID_INPUT", "--resolution 1080p not supported on 2.0-fast")

    content = build_content(
        text=text,
        images=images,
        videos=videos,
        audios=audios,
        model=params.model,
        budget=budget,
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
