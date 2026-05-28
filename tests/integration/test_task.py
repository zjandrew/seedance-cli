# tests/integration/test_task.py
import json
from pathlib import Path
from types import SimpleNamespace

from click.testing import CliRunner

from seedance_cli.__main__ import root
from tests.conftest import FakeArk


def _cli() -> CliRunner:
    return CliRunner()


def test_task_list_empty(tmp_config: Path, fake_ark: FakeArk) -> None:
    res = _cli().invoke(root, ["task", "list"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)["data"]
    assert data["tasks"] == []


def test_task_list_with_items(tmp_config: Path, fake_ark: FakeArk) -> None:
    fake_ark.content_generation.tasks.list_response = [
        SimpleNamespace(id="cgt-1", status="succeeded", model="doubao-seedance-2-0-260128"),
        SimpleNamespace(id="cgt-2", status="running", model="doubao-seedance-2-0-260128"),
    ]
    res = _cli().invoke(root, ["task", "list"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)["data"]
    assert len(data["tasks"]) == 2
    assert {t["task_id"] for t in data["tasks"]} == {"cgt-1", "cgt-2"}


def test_task_get(tmp_config: Path, fake_ark: FakeArk) -> None:
    fake_ark.content_generation.tasks.scripted_statuses = ["running"]
    res = _cli().invoke(root, ["task", "get", "cgt-1"])
    assert res.exit_code == 0, res.output
    data = json.loads(res.output)["data"]
    assert data["task_id"] == "cgt-1"
    assert data["status"] == "running"


def test_task_get_wait_and_download(tmp_config: Path, tmp_path: Path, fake_ark: FakeArk) -> None:
    import httpx
    import respx

    fake_ark.content_generation.tasks.scripted_statuses = ["running", "succeeded"]
    fake_ark.content_generation.tasks.response_extras = {"video_url": "https://fake/v.mp4"}
    out = tmp_path / "v.mp4"
    with respx.mock:
        respx.get("https://fake/v.mp4").mock(return_value=httpx.Response(200, content=b"VID"))
        res = _cli().invoke(
            root,
            [
                "task",
                "get",
                "cgt-1",
                "--wait",
                "--out",
                str(out),
                "--poll-interval",
                "0",
            ],
        )
    assert res.exit_code == 0, res.output
    assert out.read_bytes() == b"VID"


def test_task_delete(tmp_config: Path, fake_ark: FakeArk) -> None:
    res = _cli().invoke(root, ["task", "delete", "cgt-1"])
    assert res.exit_code == 0, res.output
    assert fake_ark.content_generation.tasks.deleted == ["cgt-1"]
    data = json.loads(res.output)["data"]
    assert data == {"task_id": "cgt-1", "deleted": True}
