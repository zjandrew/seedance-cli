# src/seedance_cli/core/media_io.py
from __future__ import annotations

import base64
from dataclasses import dataclass
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
            return MediaRef(
                raw=head,
                role=tail,
                is_url=is_url or head.startswith(("http://", "https://")),
            )
    return MediaRef(raw=arg, role=None, is_url=is_url)


def format_allowed(ext: str, kind: MediaKind, model_full_id: str) -> bool:
    ext = ext.lower()
    if kind == "image":
        if ext in IMAGE_EXTS_CORE:
            return True
        return ext in {"heic", "heif"} and model_full_id in IMAGE_EXTS_HEIC_MODELS
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


def to_payload(
    ref: MediaRef, *, kind: MediaKind, model: str, budget: RequestBudget
) -> dict[str, Any]:
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
                f"{kind} file {path.name} is {size / 1024 / 1024:.1f} MB; "
                f"limit is {_LIMIT_LABEL[kind]}",
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
