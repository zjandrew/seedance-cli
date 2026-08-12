# src/seedance_cli/core/content.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from seedance_cli.core.client import capability_of, expand_model
from seedance_cli.core.media_io import MediaRef, RequestBudget, to_payload
from seedance_cli.framework.errors import CliError

# "reference_image" is the role Ark demands for image inputs in reference-media
# mode (i.e. whenever a reference_audio item is present); "reference" is the role
# used by the standalone multi-image reference path. Both are accepted as inputs.
VALID_IMAGE_ROLES = {"first_frame", "last_frame", "reference", "reference_image"}
VALID_VIDEO_ROLES = {"reference"}
VALID_AUDIO_ROLES = {"reference_audio"}
# Ark requires every audio item in reference-media mode to carry this role;
# the CLI defaults to it when --audio is passed without an explicit :role.
DEFAULT_AUDIO_ROLE = "reference_audio"


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
    pair_roles = {"first_frame", "last_frame"}
    # Clean first+last pair → first_last_frame.
    if pair_roles <= roles:
        return "first_last_frame"
    # Any partial first/last role usage routes to first_last_frame so the
    # downstream validator can raise a clear pair-mismatch error — EXCEPT
    # for a lone :first_frame on a single image, which is just a redundantly
    # tagged i2v.
    if roles & pair_roles:
        if n_img == 1 and roles == {"first_frame"}:
            return "image_to_video_first"
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
    caps = capability_of(full)

    if text is None and not images and not videos and not audios:
        raise CliError(
            "INVALID_INPUT",
            "no content: pass -p TEXT or at least one --image/--video/--audio",
        )

    if len(videos) > caps.max_videos:
        raise CliError("INVALID_INPUT", f"too many videos ({len(videos)}); max {caps.max_videos}")
    if len(audios) > caps.max_audios:
        raise CliError("INVALID_INPUT", f"too many audios ({len(audios)}); max {caps.max_audios}")

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
        if not caps.multimodal_reference:
            raise CliError(
                "INVALID_INPUT",
                f"multimodal reference (multiple images, no role) not supported on {model}",
                details={"model": full},
            )
        if not (1 <= len(images) <= caps.max_ref_images):
            raise CliError(
                "INVALID_INPUT",
                f"multimodal reference allows 1-{caps.max_ref_images} images, got {len(images)}",
            )

    if (videos or audios) and not caps.video_audio_input:
        raise CliError(
            "INVALID_INPUT",
            f"video/audio input not supported on {model}",
        )

    # Ark rejects audio reference as the sole reference input ("reference_audio
    # cannot be the only reference input"). It must accompany a visual reference,
    # so pair --audio with at least one --image or --video.
    if audios and not images and not videos:
        raise CliError(
            "INVALID_INPUT",
            "reference audio cannot be the only reference input; "
            "pair --audio with at least one --image or --video",
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
        if ref.role and ref.role not in VALID_AUDIO_ROLES:
            raise CliError("INVALID_INPUT", f"invalid audio role {ref.role!r}")
        payload = to_payload(ref, kind="audio", model=full, budget=budget)
        payload.setdefault("role", DEFAULT_AUDIO_ROLE)
        content.append(payload)
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
    caps = capability_of(full)

    if params.duration is not None and params.frames is not None:
        raise CliError("INVALID_INPUT", "--duration and --frames are mutually exclusive")

    if params.frames is not None:
        if not caps.frames:
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
        if caps.duration_range is None:
            raise CliError(
                "INVALID_INPUT",
                f"--duration not supported for unrecognized model {params.model!r}",
            )
        lo, hi = caps.duration_range
        if not (lo <= params.duration <= hi):
            raise CliError(
                "INVALID_INPUT",
                f"--duration must be in [{lo},{hi}] for {params.model}; got {params.duration}",
            )

    if params.generate_audio is not None and not caps.generate_audio:
        raise CliError("INVALID_INPUT", f"--generate-audio not supported on {params.model}")

    if params.camera_fixed is not None and not caps.camera_fixed:
        raise CliError("INVALID_INPUT", f"--camera-fixed not supported on {params.model}")

    if params.service_tier == "flex" and not caps.flex:
        raise CliError(
            "INVALID_INPUT",
            f"--service-tier flex not supported on {params.model}",
        )

    if (
        params.resolution is not None
        and caps.resolutions is not None
        and params.resolution not in caps.resolutions
    ):
        raise CliError(
            "INVALID_INPUT",
            f"--resolution {params.resolution} not supported on {params.model}",
        )

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
