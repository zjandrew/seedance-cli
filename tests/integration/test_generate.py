# tests/integration/test_generate.py
import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from seedance_cli.__main__ import root
from tests.conftest import FakeArk


def _cli() -> CliRunner:
    return CliRunner()


def test_dry_run_text_to_video(tmp_config: Path):
    res = _cli().invoke(
        root,
        ["--dry-run", "generate", "-p", "a cat", "--ratio", "16:9", "--duration", "5"],
    )
    assert res.exit_code == 0, res.output
    body = json.loads(res.output)["data"]
    assert body["request"]["model"] == "doubao-seedance-2-0-260128"
    assert body["request"]["content"][0]["text"] == "a cat"
    assert body["request"]["ratio"] == "16:9"
    assert body["request"]["duration"] == 5
    assert body["request"]["watermark"] is False


def test_dry_run_first_last_frame(tmp_config: Path):
    res = _cli().invoke(
        root,
        [
            "--dry-run",
            "generate",
            "-p",
            "smile",
            "--image",
            "https://x/a.png:first_frame",
            "--image",
            "https://x/b.png:last_frame",
            "--ratio",
            "16:9",
            "--duration",
            "5",
        ],
    )
    assert res.exit_code == 0, res.output
    content = json.loads(res.output)["data"]["request"]["content"]
    assert content[1]["role"] == "first_frame"
    assert content[2]["role"] == "last_frame"


def test_async_returns_task_id(tmp_config: Path, fake_ark: FakeArk) -> None:
    fake_ark.content_generation.tasks.next_task_id = "cgt-2026-abc"
    res = _cli().invoke(root, ["generate", "-p", "a cat", "--async", "--duration", "5"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)["data"]
    assert data["task_id"] == "cgt-2026-abc"
    assert data["status"] == "queued"


def test_invalid_input_frames_on_2_0(tmp_config: Path):
    res = _cli().invoke(root, ["generate", "-p", "a", "--frames", "29", "--async"])
    assert res.exit_code == 2
    err = json.loads(res.output)["error"]
    assert err["code"] == "INVALID_INPUT"
    assert "frames" in err["message"]


def test_no_content_rejected(tmp_config: Path):
    res = _cli().invoke(root, ["generate", "--async"])
    assert res.exit_code == 2
    err = json.loads(res.output)["error"]
    assert err["code"] == "INVALID_INPUT"


def test_dry_run_redacts_base64(tmp_config: Path, tmp_path: Path):
    img = tmp_path / "tiny.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
    res = _cli().invoke(
        root,
        [
            "--dry-run",
            "generate",
            "-p",
            "a",
            "--image",
            str(img),
            "--duration",
            "5",
        ],
    )
    assert res.exit_code == 0, res.output
    body_text = res.output
    assert "<base64" in body_text
    assert "AAAAAAAAAAAAAAAAAAAA" not in body_text  # raw payload not leaked


def test_blocking_download_writes_mp4(
    tmp_config: Path, tmp_path: Path, fake_ark: FakeArk, monkeypatch: pytest.MonkeyPatch
) -> None:
    import httpx
    import respx

    fake_ark.content_generation.tasks.scripted_statuses = ["queued", "running", "succeeded"]
    fake_ark.content_generation.tasks.response_extras = {"video_url": "https://fake/v.mp4"}
    out = tmp_path / "girl.mp4"

    with respx.mock:
        respx.get("https://fake/v.mp4").mock(return_value=httpx.Response(200, content=b"\x00mp4"))
        res = _cli().invoke(
            root,
            [
                "generate",
                "-p",
                "girl",
                "--duration",
                "5",
                "--poll-interval",
                "0",
                "--out",
                str(out),
            ],
        )
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)["data"]
    assert data["status"] == "succeeded"
    assert data["video_path"] == str(out)
    assert out.read_bytes() == b"\x00mp4"


def test_no_download_omits_video_path(tmp_config: Path, fake_ark: FakeArk) -> None:
    fake_ark.content_generation.tasks.scripted_statuses = ["succeeded"]
    res = _cli().invoke(
        root,
        [
            "generate",
            "-p",
            "a",
            "--duration",
            "5",
            "--no-download",
            "--poll-interval",
            "0",
        ],
    )
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)["data"]
    assert "video_url" in data
    assert "video_path" not in data


def test_task_failed_exits_6(tmp_config: Path, fake_ark: FakeArk) -> None:
    from types import SimpleNamespace

    fake_ark.content_generation.tasks.scripted_statuses = ["failed"]
    fake_ark.content_generation.tasks.response_extras = {
        "error": SimpleNamespace(code="ContentPolicy", message="bad prompt"),
    }
    res = _cli().invoke(
        root,
        [
            "generate",
            "-p",
            "a",
            "--duration",
            "5",
            "--poll-interval",
            "0",
        ],
    )
    assert res.exit_code == 6, res.output
    err = json.loads(res.output)["error"]
    assert err["code"] == "TASK_FAILED"


def test_return_last_frame_downloads_png(
    tmp_config: Path, tmp_path: Path, fake_ark: FakeArk
) -> None:
    import httpx
    import respx

    fake_ark.content_generation.tasks.scripted_statuses = ["succeeded"]
    fake_ark.content_generation.tasks.response_extras = {
        "video_url": "https://fake/v.mp4",
        "last_frame_url": "https://fake/last.png",
    }
    out = tmp_path / "v.mp4"
    lf = tmp_path / "lf.png"
    with respx.mock:
        respx.get("https://fake/v.mp4").mock(return_value=httpx.Response(200, content=b"VID"))
        respx.get("https://fake/last.png").mock(return_value=httpx.Response(200, content=b"PNG"))
        res = _cli().invoke(
            root,
            [
                "generate",
                "-p",
                "a",
                "--duration",
                "5",
                "--poll-interval",
                "0",
                "--return-last-frame",
                "--out",
                str(out),
                "--out-last-frame",
                str(lf),
            ],
        )
    assert res.exit_code == 0, res.output
    assert lf.read_bytes() == b"PNG"
