# tests/unit/core/test_content.py
import pytest

from seedance_cli.core.content import RequestParams, build_content, build_request
from seedance_cli.core.media_io import MediaRef, RequestBudget
from seedance_cli.framework.errors import CliError


def _img(raw: str, role: str | None = None) -> MediaRef:
    return MediaRef(raw=raw, role=role, is_url=raw.startswith("http"))


def _vid(raw: str, role: str | None = None) -> MediaRef:
    return MediaRef(raw=raw, role=role, is_url=raw.startswith("http"))


def _aud(raw: str, role: str | None = None) -> MediaRef:
    return MediaRef(raw=raw, role=role, is_url=raw.startswith("http"))


MODEL_2_5 = "doubao-seedance-2-5-260628"
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
    # Ark requires the audio item to carry role=reference_audio (reference-media mode).
    assert out[3]["role"] == "reference_audio"


def test_audio_defaults_to_reference_role():
    """--audio without an explicit :role must still send role=reference_audio,
    otherwise Ark 400s: 'reference media mode requires audio role to be reference_audio'.
    Audio must accompany a visual reference, so pair it with an image here."""
    out = build_content(
        text="a",
        images=[_img("https://x/a.png")],
        videos=[],
        audios=[_aud("https://x/s.mp3")],
        model=MODEL_2_0,
        budget=RequestBudget(),
    )
    audio = next(c for c in out if c["type"] == "audio_url")
    assert audio["role"] == "reference_audio"


def test_audio_explicit_valid_role_preserved():
    out = build_content(
        text="a",
        images=[_img("https://x/a.png")],
        videos=[],
        audios=[_aud("https://x/s.mp3", role="reference_audio")],
        model=MODEL_2_0,
        budget=RequestBudget(),
    )
    audio = next(c for c in out if c["type"] == "audio_url")
    assert audio["role"] == "reference_audio"


def test_audio_invalid_role_rejected():
    with pytest.raises(CliError) as ei:
        build_content(
            text="a",
            images=[_img("https://x/a.png")],
            videos=[],
            audios=[_aud("https://x/s.mp3", role="bogus")],
            model=MODEL_2_0,
            budget=RequestBudget(),
        )
    assert ei.value.code == "INVALID_INPUT"


def test_audio_only_reference_rejected():
    """Ark: 'reference_audio cannot be the only reference input' — the CLI should
    catch this pre-flight when --audio is passed with no --image/--video."""
    with pytest.raises(CliError) as ei:
        build_content(
            text="a",
            images=[],
            videos=[],
            audios=[_aud("https://x/s.mp3")],
            model=MODEL_2_0,
            budget=RequestBudget(),
        )
    assert ei.value.code == "INVALID_INPUT"
    assert "only reference" in ei.value.message


def test_image_reference_image_role_preserved():
    """Reference-media (audio) mode requires the image role to be reference_image;
    Ark 400s otherwise: 'reference media mode requires all image roles to be
    reference_image'. The role must be a valid input and survive into the payload."""
    out = build_content(
        text="speak",
        images=[_img("https://x/a.png", role="reference_image")],
        videos=[],
        audios=[_aud("https://x/s.mp3", role="reference_audio")],
        model=MODEL_2_0,
        budget=RequestBudget(),
    )
    image = next(c for c in out if c["type"] == "image_url")
    assert image["role"] == "reference_image"


def test_single_image_with_first_frame_role_is_still_i2v():
    """A lone :first_frame on a single image is a redundantly tagged i2v,
    not a malformed first/last pair. (Validated against real Ark API.)"""
    refs = [_img("https://x/a.png", role="first_frame")]
    out = build_content(
        text="a", images=refs, videos=[], audios=[], model=MODEL_2_0, budget=RequestBudget()
    )
    image_items = [c for c in out if c["type"] == "image_url"]
    assert len(image_items) == 1


def test_single_image_with_last_frame_role_alone_rejected():
    """Lone :last_frame on a single image is malformed — first/last pair without first."""
    refs = [_img("https://x/a.png", role="last_frame")]
    with pytest.raises(CliError) as ei:
        build_content(
            text="a", images=refs, videos=[], audios=[], model=MODEL_2_0, budget=RequestBudget()
        )
    assert ei.value.code == "INVALID_INPUT"


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


# ---- seedance 2.5 capability surface (docs 82379/1520757, 2607688) ----


def test_build_request_2_5_duration_range_4_to_30():
    out = build_request(
        params=RequestParams(model="2.5", duration=30),
        text="a",
        images=[],
        videos=[],
        audios=[],
        budget=RequestBudget(),
    )
    assert out["model"] == MODEL_2_5
    assert out["duration"] == 30
    for bad in (3, 31):
        with pytest.raises(CliError):
            build_request(
                params=RequestParams(model="2.5", duration=bad),
                text="a",
                images=[],
                videos=[],
                audios=[],
                budget=RequestBudget(),
            )


def test_build_request_duration_minus_one_model_decides():
    # -1 = let the model pick the duration; supported on 2.5 / 2.0 series / 1.5-pro.
    for m in ("2.5", "2.0", "2.0-fast", "1.5-pro"):
        out = build_request(
            params=RequestParams(model=m, duration=-1),
            text="a",
            images=[],
            videos=[],
            audios=[],
            budget=RequestBudget(),
        )
        assert out["duration"] == -1, m


def test_build_request_duration_minus_one_rejected_on_1_0_pro():
    # Docs: 1.0-pro / 1.0-pro-fast take [2,12] only, no -1.
    with pytest.raises(CliError) as ei:
        build_request(
            params=RequestParams(model="1.0-pro", duration=-1),
            text="a",
            images=[],
            videos=[],
            audios=[],
            budget=RequestBudget(),
        )
    assert ei.value.code == "INVALID_INPUT"


def test_build_request_1080p_rejected_on_2_5():
    # 2.5 supports 480p/720p only.
    with pytest.raises(CliError) as ei:
        build_request(
            params=RequestParams(model="2.5", resolution="1080p"),
            text="a",
            images=[],
            videos=[],
            audios=[],
            budget=RequestBudget(),
        )
    assert "1080p" in ei.value.message


def test_build_request_720p_accepted_on_2_5():
    out = build_request(
        params=RequestParams(model="2.5", resolution="720p"),
        text="a",
        images=[],
        videos=[],
        audios=[],
        budget=RequestBudget(),
    )
    assert out["resolution"] == "720p"


def test_multimodal_reference_2_5_allows_30_images():
    refs = [_img(f"https://x/{i}.png") for i in range(30)]
    out = build_content(
        text="a", images=refs, videos=[], audios=[], model=MODEL_2_5, budget=RequestBudget()
    )
    assert sum(1 for c in out if c["type"] == "image_url") == 30
    with pytest.raises(CliError):
        build_content(
            text="a",
            images=[*refs, _img("https://x/31.png")],
            videos=[],
            audios=[],
            model=MODEL_2_5,
            budget=RequestBudget(),
        )


def test_video_caps_10_on_2_5_but_3_on_2_0():
    vids = [_vid(f"https://x/{i}.mp4") for i in range(10)]
    out = build_content(
        text="a", images=[], videos=vids, audios=[], model=MODEL_2_5, budget=RequestBudget()
    )
    assert sum(1 for c in out if c["type"] == "video_url") == 10
    with pytest.raises(CliError):
        build_content(
            text="a",
            images=[],
            videos=vids[:4],
            audios=[],
            model=MODEL_2_0,
            budget=RequestBudget(),
        )


def test_audio_only_allowed_on_2_5():
    # 2.5 accepts audio as the sole reference input (2.0 series does not).
    out = build_content(
        text="a talking head",
        images=[],
        videos=[],
        audios=[_aud("https://x/s.mp3")],
        model=MODEL_2_5,
        budget=RequestBudget(),
    )
    audio = next(c for c in out if c["type"] == "audio_url")
    assert audio["role"] == "reference_audio"


def test_video_role_reference_video_accepted():
    # Docs-canonical video role (2.5 and 2.0 series): reference_video.
    out = build_content(
        text="extend it",
        images=[],
        videos=[_vid("https://x/v.mp4", role="reference_video")],
        audios=[],
        model=MODEL_2_5,
        budget=RequestBudget(),
    )
    video = next(c for c in out if c["type"] == "video_url")
    assert video["role"] == "reference_video"


def test_2_5_defaults_reference_roles():
    """Docs 1520757: on 2.5 the reference roles are mandatory — reference_image on
    reference images, reference_video on videos. Role-less inputs would otherwise
    be ambiguous (role-less image = first_frame) and fail asynchronously."""
    out = build_content(
        text="a",
        images=[_img("https://x/a.png"), _img("https://x/b.png")],
        videos=[_vid("https://x/v.mp4")],
        audios=[],
        model=MODEL_2_5,
        budget=RequestBudget(),
    )
    images = [c for c in out if c["type"] == "image_url"]
    videos = [c for c in out if c["type"] == "video_url"]
    assert all(i["role"] == "reference_image" for i in images)
    assert all(v["role"] == "reference_video" for v in videos)


def test_2_5_single_roleless_image_stays_first_frame():
    # i2v: a lone role-less image means first_frame (role omitted) — do not
    # rewrite it into a reference_image.
    out = build_content(
        text="a",
        images=[_img("https://x/a.png")],
        videos=[],
        audios=[],
        model=MODEL_2_5,
        budget=RequestBudget(),
    )
    image = next(c for c in out if c["type"] == "image_url")
    assert "role" not in image


def test_2_0_roleless_reference_inputs_unchanged():
    # 2.0 was validated against the real API with role-less multi-image and
    # role-less video inputs — keep sending them untouched.
    out = build_content(
        text="a",
        images=[_img("https://x/a.png"), _img("https://x/b.png")],
        videos=[_vid("https://x/v.mp4")],
        audios=[],
        model=MODEL_2_0,
        budget=RequestBudget(),
    )
    for c in out:
        if c["type"] in ("image_url", "video_url"):
            assert "role" not in c


def test_build_request_generate_audio_accepted_on_2_5():
    out = build_request(
        params=RequestParams(model="2.5", generate_audio=False),
        text="a",
        images=[],
        videos=[],
        audios=[],
        budget=RequestBudget(),
    )
    assert out["generate_audio"] is False


# ---- 2.0 series gap fixes: 2.0-mini, 4k tier (docs 82379/2291680) ----


def test_build_request_4k_accepted_on_2_0_only():
    out = build_request(
        params=RequestParams(model="2.0", resolution="4k"),
        text="a",
        images=[],
        videos=[],
        audios=[],
        budget=RequestBudget(),
    )
    assert out["resolution"] == "4k"
    for m in ("2.5", "2.0-fast", "2.0-mini"):
        with pytest.raises(CliError) as ei:
            build_request(
                params=RequestParams(model=m, resolution="4k"),
                text="a",
                images=[],
                videos=[],
                audios=[],
                budget=RequestBudget(),
            )
        assert "4k" in ei.value.message, m


def test_build_request_2_0_mini_capability_matches_2_0_series():
    # duration [4,15] or -1; video/audio reference inputs allowed
    out = build_request(
        params=RequestParams(model="2.0-mini", duration=-1),
        text="a",
        images=[],
        videos=[_vid("https://x/v.mp4")],
        audios=[],
        budget=RequestBudget(),
    )
    assert out["model"] == "doubao-seedance-2-0-mini-260615"
    assert out["duration"] == -1
    with pytest.raises(CliError):
        build_request(
            params=RequestParams(model="2.0-mini", duration=16),
            text="a",
            images=[],
            videos=[],
            audios=[],
            budget=RequestBudget(),
        )


# ---- generation-gated params + 2.5 forced constraints (#10) ----


def test_build_request_seed_rejected_on_2_x():
    # Docs: seed is 1.x-only (1.5-pro / 1.0-pro / 1.0-pro-fast).
    for m in ("2.5", "2.0", "2.0-fast", "2.0-mini"):
        with pytest.raises(CliError) as ei:
            build_request(
                params=RequestParams(model=m, seed=42),
                text="a",
                images=[],
                videos=[],
                audios=[],
                budget=RequestBudget(),
            )
        assert "seed" in ei.value.message, m


def test_build_request_seed_passthrough_on_unknown_model():
    # ADR-0001: only documented prohibitions are gated; future models pass through.
    out = build_request(
        params=RequestParams(model="doubao-seedance-9-9-999999", seed=7),
        text="a",
        images=[],
        videos=[],
        audios=[],
        budget=RequestBudget(),
    )
    assert out["seed"] == 7


def test_build_request_ratio_forced_adaptive_on_2_5_image_scenarios():
    # 2.5 docs: first-frame / first+last-frame tasks force ratio=adaptive.
    with pytest.raises(CliError) as ei:
        build_request(
            params=RequestParams(model="2.5", ratio="16:9"),
            text="a",
            images=[_img("https://x/a.png")],
            videos=[],
            audios=[],
            budget=RequestBudget(),
        )
    assert "adaptive" in ei.value.message
    with pytest.raises(CliError):
        build_request(
            params=RequestParams(model="2.5", ratio="16:9"),
            text="a",
            images=[
                _img("https://x/a.png", role="first_frame"),
                _img("https://x/b.png", role="last_frame"),
            ],
            videos=[],
            audios=[],
            budget=RequestBudget(),
        )
    # ratio=adaptive (or omitted) is fine
    out = build_request(
        params=RequestParams(model="2.5", ratio="adaptive"),
        text="a",
        images=[_img("https://x/a.png")],
        videos=[],
        audios=[],
        budget=RequestBudget(),
    )
    assert out["ratio"] == "adaptive"


def test_build_request_ratio_free_where_2_5_allows_it():
    # text-to-video and multimodal reference carry no ratio restriction on 2.5;
    # video with task type auto is ambiguous (could be pure reference) → pass through.
    out = build_request(
        params=RequestParams(model="2.5", ratio="16:9"),
        text="a",
        images=[],
        videos=[],
        audios=[],
        budget=RequestBudget(),
    )
    assert out["ratio"] == "16:9"
    out = build_request(
        params=RequestParams(model="2.5", ratio="16:9"),
        text="a",
        images=[_img("https://x/a.png"), _img("https://x/b.png")],
        videos=[],
        audios=[],
        budget=RequestBudget(),
    )
    assert out["ratio"] == "16:9"
    out = build_request(
        params=RequestParams(model="2.5", ratio="16:9"),
        text="a",
        images=[],
        videos=[_vid("https://x/v.mp4")],
        audios=[],
        budget=RequestBudget(),
    )
    assert out["ratio"] == "16:9"


def test_build_request_ratio_not_forced_on_2_0():
    out = build_request(
        params=RequestParams(model="2.0", ratio="16:9"),
        text="a",
        images=[_img("https://x/a.png")],
        videos=[],
        audios=[],
        budget=RequestBudget(),
    )
    assert out["ratio"] == "16:9"


def test_build_request_2_5_explicit_edit_extend_force_adaptive_ratio():
    for tt in ("edit", "extend"):
        with pytest.raises(CliError) as ei:
            build_request(
                params=RequestParams(model="2.5", ratio="16:9", task_type=tt),
                text="repaint walls blue",
                images=[],
                videos=[_vid("https://x/v.mp4")],
                audios=[],
                budget=RequestBudget(),
            )
        assert "adaptive" in ei.value.message, tt


def test_build_request_2_5_edit_requires_duration_minus_one():
    with pytest.raises(CliError) as ei:
        build_request(
            params=RequestParams(model="2.5", task_type="edit", duration=10),
            text="repaint walls blue",
            images=[],
            videos=[_vid("https://x/v.mp4")],
            audios=[],
            budget=RequestBudget(),
        )
    assert "-1" in ei.value.message
    out = build_request(
        params=RequestParams(model="2.5", task_type="edit", duration=-1),
        text="repaint walls blue",
        images=[],
        videos=[_vid("https://x/v.mp4")],
        audios=[],
        budget=RequestBudget(),
    )
    assert out["duration"] == -1
    # extend may customize duration
    out = build_request(
        params=RequestParams(model="2.5", task_type="extend", duration=10),
        text="extend the shot",
        images=[],
        videos=[_vid("https://x/v.mp4")],
        audios=[],
        budget=RequestBudget(),
    )
    assert out["duration"] == 10


def test_first_last_roles_cannot_mix_with_reference_media():
    # Docs: first/last-frame and omni-reference are mutually exclusive scenarios.
    with pytest.raises(CliError) as ei:
        build_content(
            text="a",
            images=[_img("https://x/a.png", role="first_frame")],
            videos=[_vid("https://x/v.mp4")],
            audios=[],
            model=MODEL_2_0,
            budget=RequestBudget(),
        )
    assert ei.value.code == "INVALID_INPUT"


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
