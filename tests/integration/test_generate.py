# tests/integration/test_generate.py
import json
from pathlib import Path

from click.testing import CliRunner

from seedance_cli.__main__ import root


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
