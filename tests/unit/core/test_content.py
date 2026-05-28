# tests/unit/core/test_content.py
import pytest

from seedance_cli.core.content import RequestParams, build_content, build_request
from seedance_cli.core.media_io import MediaRef, RequestBudget
from seedance_cli.framework.errors import CliError


def _img(raw: str, role: str | None = None) -> MediaRef:
    return MediaRef(raw=raw, role=role, is_url=raw.startswith("http"))


def _vid(raw: str, role: str | None = None) -> MediaRef:
    return MediaRef(raw=raw, role=role, is_url=raw.startswith("http"))


def _aud(raw: str) -> MediaRef:
    return MediaRef(raw=raw, role=None, is_url=raw.startswith("http"))


MODEL_2_0 = "doubao-seedance-2-0-260128"
MODEL_2_0_FAST = "doubao-seedance-2-0-fast-260128"
MODEL_1_5_PRO = "doubao-seedance-1-5-pro-251215"
MODEL_1_0_PRO = "doubao-seedance-1-0-pro-250528"


# ---- scenarios ----


def test_text_to_video():
    out = build_content(
        text="a cat", images=[], videos=[], audios=[], model=MODEL_2_0, budget=RequestBudget()
    )
    assert len(out) == 1
    assert out[0]["type"] == "text"
    assert out[0]["text"] == "a cat"


def test_image_to_video_first_frame_implicit():
    refs = [_img("https://x/a.png")]
    out = build_content(
        text="a", images=refs, videos=[], audios=[], model=MODEL_2_0, budget=RequestBudget()
    )
    types = [c["type"] for c in out]
    assert types == ["text", "image_url"]
    assert "role" not in out[1]


def test_first_last_frame_pair():
    refs = [
        _img("https://x/a.png", role="first_frame"),
        _img("https://x/b.png", role="last_frame"),
    ]
    out = build_content(
        text="a", images=refs, videos=[], audios=[], model=MODEL_2_0, budget=RequestBudget()
    )
    assert out[1]["role"] == "first_frame"
    assert out[2]["role"] == "last_frame"


def test_multimodal_reference_2_0():
    refs = [_img(f"https://x/{i}.png") for i in range(5)]
    out = build_content(
        text="a", images=refs, videos=[], audios=[], model=MODEL_2_0, budget=RequestBudget()
    )
    assert sum(1 for c in out if c["type"] == "image_url") == 5


def test_video_edit_2_0():
    out = build_content(
        text="repaint blue",
        images=[],
        videos=[_vid("https://x/v.mp4")],
        audios=[],
        model=MODEL_2_0,
        budget=RequestBudget(),
    )
    types = [c["type"] for c in out]
    assert types == ["text", "video_url"]


def test_combo_image_video_audio_2_0():
    out = build_content(
        text="combo",
        images=[_img("https://x/a.png")],
        videos=[_vid("https://x/v.mp4")],
        audios=[_aud("https://x/s.mp3")],
        model=MODEL_2_0,
        budget=RequestBudget(),
    )
    types = [c["type"] for c in out]
    assert types == ["text", "image_url", "video_url", "audio_url"]


# ---- count limits ----


def test_too_many_images_for_multimodal_ref():
    refs = [_img(f"https://x/{i}.png") for i in range(10)]
    with pytest.raises(CliError) as ei:
        build_content(
            text="a", images=refs, videos=[], audios=[], model=MODEL_2_0, budget=RequestBudget()
        )
    assert ei.value.code == "INVALID_INPUT"


def test_multimodal_ref_requires_2_0_series():
    refs = [_img(f"https://x/{i}.png") for i in range(3)]
    with pytest.raises(CliError) as ei:
        build_content(
            text="a", images=refs, videos=[], audios=[], model=MODEL_1_5_PRO, budget=RequestBudget()
        )
    assert "multimodal" in ei.value.message.lower() or "2.0" in ei.value.message


def test_first_last_pair_only_first_role_rejected():
    refs = [_img("https://x/a.png", role="first_frame"), _img("https://x/b.png")]
    with pytest.raises(CliError) as ei:
        build_content(
            text="a", images=refs, videos=[], audios=[], model=MODEL_2_0, budget=RequestBudget()
        )
    assert ei.value.code == "INVALID_INPUT"


def test_text_optional_when_image_present():
    out = build_content(
        text=None,
        images=[_img("https://x/a.png")],
        videos=[],
        audios=[],
        model=MODEL_2_0,
        budget=RequestBudget(),
    )
    assert all(c["type"] != "text" for c in out)


def test_empty_request_rejected():
    with pytest.raises(CliError) as ei:
        build_content(
            text=None, images=[], videos=[], audios=[], model=MODEL_2_0, budget=RequestBudget()
        )
    assert ei.value.code == "INVALID_INPUT"


def test_too_many_videos():
    refs = [_vid(f"https://x/{i}.mp4") for i in range(4)]
    with pytest.raises(CliError) as ei:
        build_content(
            text="a", images=[], videos=refs, audios=[], model=MODEL_2_0, budget=RequestBudget()
        )
    assert ei.value.code == "INVALID_INPUT"


def test_too_many_audios():
    refs = [_aud(f"https://x/{i}.mp3") for i in range(4)]
    with pytest.raises(CliError) as ei:
        build_content(
            text="a", images=[], videos=[], audios=refs, model=MODEL_2_0, budget=RequestBudget()
        )
    assert ei.value.code == "INVALID_INPUT"


# ---- build_request: top-level params ----


def test_build_request_minimal():
    params = RequestParams(model="2.0", ratio="16:9", duration=5)
    out = build_request(
        params=params, text="a", images=[], videos=[], audios=[], budget=RequestBudget()
    )
    assert out["model"] == MODEL_2_0
    assert out["ratio"] == "16:9"
    assert out["duration"] == 5
    assert "watermark" in out
    assert out["watermark"] is False


def test_build_request_generate_audio_requires_supported_model():
    params = RequestParams(model="1.0-pro", generate_audio=True)
    with pytest.raises(CliError) as ei:
        build_request(
            params=params, text="a", images=[], videos=[], audios=[], budget=RequestBudget()
        )
    assert "generate_audio" in ei.value.message or "generate-audio" in ei.value.message


def test_build_request_frames_only_on_1_0_pro():
    params = RequestParams(model="2.0", frames=29)
    with pytest.raises(CliError) as ei:
        build_request(
            params=params, text="a", images=[], videos=[], audios=[], budget=RequestBudget()
        )
    assert "frames" in ei.value.message


def test_build_request_frames_grid_check():
    params = RequestParams(model="1.0-pro", frames=30)  # 30 != 25 + 4n
    with pytest.raises(CliError) as ei:
        build_request(
            params=params, text="a", images=[], videos=[], audios=[], budget=RequestBudget()
        )
    assert "frames" in ei.value.message


def test_build_request_duration_and_frames_mutually_exclusive():
    params = RequestParams(model="1.0-pro", duration=5, frames=29)
    with pytest.raises(CliError) as ei:
        build_request(
            params=params, text="a", images=[], videos=[], audios=[], budget=RequestBudget()
        )
    assert "duration" in ei.value.message and "frames" in ei.value.message


def test_build_request_flex_rejected_on_2_0():
    params = RequestParams(model="2.0", service_tier="flex")
    with pytest.raises(CliError) as ei:
        build_request(
            params=params, text="a", images=[], videos=[], audios=[], budget=RequestBudget()
        )
    assert "flex" in ei.value.message.lower() or "service" in ei.value.message.lower()


def test_build_request_1080p_rejected_on_2_0_fast():
    params = RequestParams(model="2.0-fast", resolution="1080p")
    with pytest.raises(CliError) as ei:
        build_request(
            params=params, text="a", images=[], videos=[], audios=[], budget=RequestBudget()
        )
    assert "1080p" in ei.value.message


def test_build_request_duration_range_per_model():
    # 2.0: 4-15
    with pytest.raises(CliError):
        build_request(
            params=RequestParams(model="2.0", duration=3),
            text="a",
            images=[],
            videos=[],
            audios=[],
            budget=RequestBudget(),
        )
    # 1.0-pro: 2-12
    out = build_request(
        params=RequestParams(model="1.0-pro", duration=2),
        text="a",
        images=[],
        videos=[],
        audios=[],
        budget=RequestBudget(),
    )
    assert out["duration"] == 2


def test_build_request_camera_fixed_only_on_supported_models():
    with pytest.raises(CliError) as ei:
        build_request(
            params=RequestParams(model="2.0", camera_fixed=True),
            text="a",
            images=[],
            videos=[],
            audios=[],
            budget=RequestBudget(),
        )
    assert "camera" in ei.value.message.lower()


def test_build_request_duration_unknown_model_raises_invalid_input():
    # Forward-compat models in client.expand_model don't have duration ranges yet.
    # Should raise CliError, NOT KeyError.
    params = RequestParams(model="doubao-seedance-9-9-999999", duration=5)
    with pytest.raises(CliError) as ei:
        build_request(
            params=params, text="a", images=[], videos=[], audios=[], budget=RequestBudget()
        )
    assert ei.value.code == "INVALID_INPUT"


def test_build_request_duration_upper_bound_per_model():
    # 1.5-pro upper bound is 12 (different from 2.0's 15) — verify it's enforced.
    with pytest.raises(CliError):
        build_request(
            params=RequestParams(model="1.5-pro", duration=13),
            text="a",
            images=[],
            videos=[],
            audios=[],
            budget=RequestBudget(),
        )
    # 2.0 upper bound is 15.
    with pytest.raises(CliError):
        build_request(
            params=RequestParams(model="2.0", duration=16),
            text="a",
            images=[],
            videos=[],
            audios=[],
            budget=RequestBudget(),
        )
    # 2.0 duration=15 should be accepted.
    out = build_request(
        params=RequestParams(model="2.0", duration=15),
        text="a",
        images=[],
        videos=[],
        audios=[],
        budget=RequestBudget(),
    )
    assert out["duration"] == 15


def test_build_request_pass_through_fields():
    # seed, callback_url, execution_expires_after, return_last_frame must all
    # land in the request body so the SDK forwards them to Ark.
    params = RequestParams(
        model="1.5-pro",
        duration=5,
        seed=42,
        callback_url="https://example.com/hook",
        service_tier="flex",
        execution_expires_after=7200,
        return_last_frame=True,
    )
    out = build_request(
        params=params, text="a", images=[], videos=[], audios=[], budget=RequestBudget()
    )
    assert out["seed"] == 42
    assert out["callback_url"] == "https://example.com/hook"
    assert out["service_tier"] == "flex"
    assert out["execution_expires_after"] == 7200
    assert out["return_last_frame"] is True


def test_build_request_1_0_pro_fast_frames_accepted():
    # 1.0-pro-fast is in _FRAMES_CAPABLE but never directly tested.
    out = build_request(
        params=RequestParams(model="1.0-pro-fast", frames=29),
        text="a",
        images=[],
        videos=[],
        audios=[],
        budget=RequestBudget(),
    )
    assert out["frames"] == 29
