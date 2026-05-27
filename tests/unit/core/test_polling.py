# tests/unit/core/test_polling.py
from types import SimpleNamespace

import pytest

from seedance_cli.core.polling import poll_until_done
from seedance_cli.framework.errors import CliError


class FakeTasksAPI:
    def __init__(self, scripted: list[SimpleNamespace]):
        self._scripted = scripted
        self.calls = 0

    def get(self, task_id: str) -> SimpleNamespace:
        self.calls += 1
        return self._scripted[min(self.calls - 1, len(self._scripted) - 1)]


def _resp(status: str, **extra) -> SimpleNamespace:
    return SimpleNamespace(id="cgt-1", status=status, **extra)


def test_poll_succeeds_after_a_few_running():
    api = FakeTasksAPI(
        [
            _resp("queued"),
            _resp("running"),
            _resp("running"),
            _resp("succeeded", content=SimpleNamespace(video_url="https://x")),
        ]
    )
    out = poll_until_done(api, task_id="cgt-1", interval=0.0)
    assert out.status == "succeeded"
    assert out.poll_count == 4
    assert out.elapsed_seconds >= 0


def test_poll_failed_raises_task_failed():
    api = FakeTasksAPI(
        [
            _resp("running"),
            _resp("failed", error=SimpleNamespace(code="X", message="bad")),
        ]
    )
    with pytest.raises(CliError) as ei:
        poll_until_done(api, task_id="cgt-1", interval=0.0)
    assert ei.value.code == "TASK_FAILED"
    assert "bad" in (ei.value.details or {}).get("error", {}).get("message", "")


def test_poll_expired_raises_task_expired():
    api = FakeTasksAPI([_resp("expired")])
    with pytest.raises(CliError) as ei:
        poll_until_done(api, task_id="cgt-1", interval=0.0)
    assert ei.value.code == "TASK_EXPIRED"


def test_poll_timeout_raises():
    api = FakeTasksAPI([_resp("running")])
    with pytest.raises(CliError) as ei:
        poll_until_done(api, task_id="cgt-1", interval=0.0, timeout=0.0)
    assert ei.value.code == "POLL_TIMEOUT"
    assert (ei.value.details or {}).get("task_id") == "cgt-1"


def test_poll_emits_progress_callback():
    api = FakeTasksAPI(
        [
            _resp("queued"),
            _resp("running"),
            _resp("succeeded"),
        ]
    )
    events: list[tuple[str, int]] = []
    poll_until_done(
        api,
        task_id="cgt-1",
        interval=0.0,
        on_status=lambda s, n: events.append((s, n)),
    )
    assert events == [("queued", 1), ("running", 2), ("succeeded", 3)]
