# tests/conftest.py
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


@dataclass
class FakeTasks:
    created: list[dict[str, Any]] = field(default_factory=list)
    scripted_statuses: list[str] = field(default_factory=lambda: ["succeeded"])
    next_task_id: str = "cgt-2026-fake000001"
    response_extras: dict[str, Any] = field(default_factory=dict)
    list_response: list[Any] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    _status_idx: int = 0

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.created.append(kwargs)
        return SimpleNamespace(id=self.next_task_id)

    def get(self, task_id: str) -> SimpleNamespace:
        status = self.scripted_statuses[min(self._status_idx, len(self.scripted_statuses) - 1)]
        self._status_idx += 1
        extras = dict(self.response_extras)
        if status == "succeeded":
            extras.setdefault(
                "content",
                SimpleNamespace(
                    video_url=extras.pop("video_url", "https://fake/v.mp4"),
                    last_frame_url=extras.pop("last_frame_url", None),
                ),
            )
        return SimpleNamespace(
            id=task_id,
            status=status,
            model="doubao-seedance-2-0-260128",
            created_at=1700000000,
            updated_at=1700000084,
            seed=42,
            ratio="16:9",
            resolution="720p",
            duration=5,
            framespersecond=24,
            service_tier="default",
            usage=SimpleNamespace(completion_tokens=1, total_tokens=1),
            **extras,
        )

    def list(self, **kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(items=self.list_response, next_page_token=None)

    def delete(self, task_id: str) -> None:
        self.deleted.append(task_id)


@dataclass
class FakeContentGeneration:
    tasks: FakeTasks = field(default_factory=FakeTasks)


@dataclass
class FakeArk:
    content_generation: FakeContentGeneration = field(default_factory=FakeContentGeneration)


@pytest.fixture
def fake_ark(monkeypatch: pytest.MonkeyPatch) -> FakeArk:
    fake = FakeArk()
    monkeypatch.setattr(
        "seedance_cli.core.client.make_ark_client",
        lambda *_a, **_k: fake,
    )
    return fake


@pytest.fixture
def tmp_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    cfg_path = tmp_path / "config.json"
    monkeypatch.setattr("seedance_cli.core.config.DEFAULT_CONFIG_PATH", cfg_path)
    # Provide a fake API key by default so the auth resolver doesn't blow up
    # unless a test explicitly clears the env.
    monkeypatch.setenv("ARK_API_KEY", "sk-test-1234567890")
    # Clear any host-leaked profile env that would change resolution.
    monkeypatch.delenv("SEEDANCE_PROFILE", raising=False)
    monkeypatch.delenv("SEEDANCE_ENDPOINT", raising=False)
    return cfg_path
