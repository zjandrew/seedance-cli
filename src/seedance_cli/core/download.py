# src/seedance_cli/core/download.py
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

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
