# tests/unit/framework/test_envelope.py
import json
import pytest
from seedance_cli.framework.envelope import Success, Failure, render, apply_jq


def test_success_renders_json():
    out = render(Success(data={"task_id": "cgt-1", "status": "succeeded"}), fmt="json")
    parsed = json.loads(out)
    assert parsed == {"ok": True, "data": {"task_id": "cgt-1", "status": "succeeded"}}


def test_failure_renders_json_with_details():
    out = render(Failure(code="INVALID_INPUT", message="bad ratio", details={"flag": "--ratio"}), fmt="json")
    parsed = json.loads(out)
    assert parsed == {"ok": False, "error": {"code": "INVALID_INPUT", "message": "bad ratio", "details": {"flag": "--ratio"}}}


def test_failure_renders_json_without_details():
    out = render(Failure(code="NETWORK_ERROR", message="boom"), fmt="json")
    parsed = json.loads(out)
    assert "details" not in parsed["error"]


def test_apply_jq_simple_path():
    env = Success(data={"task_id": "cgt-1", "nested": {"video_url": "https://x"}})
    out = apply_jq(env, ".nested.video_url")
    assert out.data == "https://x"


def test_apply_jq_array_index():
    env = Success(data={"tasks": [{"id": "a"}, {"id": "b"}]})
    out = apply_jq(env, ".tasks[1].id")
    assert out.data == "b"


def test_apply_jq_unknown_path_returns_none():
    env = Success(data={"a": 1})
    out = apply_jq(env, ".nope.missing")
    assert out.data is None


def test_render_table_dict_kv():
    out = render(Success(data={"task_id": "cgt-1", "duration": 5}), fmt="table")
    assert "task_id" in out and "cgt-1" in out and "duration" in out


def test_render_table_falls_back_to_json_for_scalar():
    out = render(Success(data="raw-string"), fmt="table")
    assert "raw-string" in out
