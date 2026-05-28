# tests/unit/core/test_download.py
from pathlib import Path

import httpx
import pytest
import respx

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
    download(
        url="https://x/y.mp4",
        out=tmp_path / "out.mp4",
        on_progress=lambda done, total: events.append((done, total)),
    )
    assert events  # at least one progress event
    assert events[-1][0] == 10
    assert events[-1][1] == 10
