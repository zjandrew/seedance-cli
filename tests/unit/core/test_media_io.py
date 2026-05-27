# tests/unit/core/test_media_io.py
from pathlib import Path

import pytest

from seedance_cli.core.media_io import (
    MAX_REQUEST_BYTES,
    MediaRef,
    RequestBudget,
    format_allowed,
    parse_ref,
    to_payload,
)
from seedance_cli.framework.errors import CliError

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"


def test_parse_ref_url_no_role():
    ref = parse_ref(
        "https://example.com/a.png",
        valid_roles={"first_frame", "last_frame", "reference"},
    )
    assert ref.raw == "https://example.com/a.png"
    assert ref.role is None
    assert ref.is_url is True


def test_parse_ref_url_with_port_is_not_split():
    ref = parse_ref(
        "https://host:8080/x.png",
        valid_roles={"first_frame", "last_frame"},
    )
    assert ref.raw == "https://host:8080/x.png"
    assert ref.role is None


def test_parse_ref_local_with_role():
    ref = parse_ref("./a.png:first_frame", valid_roles={"first_frame", "last_frame"})
    assert ref.raw == "./a.png"
    assert ref.role == "first_frame"
    assert ref.is_url is False


def test_parse_ref_local_role_invalid_means_no_split():
    # ":weird" suffix is NOT a known role → treat the whole thing as path
    ref = parse_ref("./a.png:weird", valid_roles={"first_frame", "last_frame"})
    assert ref.raw == "./a.png:weird"
    assert ref.role is None


def test_to_payload_url_passes_through():
    ref = MediaRef(raw="https://x/y.png", role=None, is_url=True)
    budget = RequestBudget()
    out = to_payload(ref, kind="image", model="2.0", budget=budget)
    assert out["type"] == "image_url"
    assert out["image_url"]["url"] == "https://x/y.png"
    assert "role" not in out
    assert budget.bytes_used == 0


def test_to_payload_local_image_base64():
    ref = MediaRef(raw=str(FIXTURES / "tiny.png"), role="first_frame", is_url=False)
    budget = RequestBudget()
    out = to_payload(ref, kind="image", model="2.0", budget=budget)
    assert out["type"] == "image_url"
    assert out["image_url"]["url"].startswith("data:image/png;base64,")
    assert out["role"] == "first_frame"
    assert budget.bytes_used > 0


def test_to_payload_rejects_unknown_extension(tmp_path: Path):
    bad = tmp_path / "tiny.txt"
    bad.write_text("hi")
    ref = MediaRef(raw=str(bad), role=None, is_url=False)
    with pytest.raises(CliError) as ei:
        to_payload(ref, kind="image", model="2.0", budget=RequestBudget())
    assert ei.value.code == "INVALID_INPUT"


def test_to_payload_rejects_file_too_large(tmp_path: Path):
    big = tmp_path / "big.png"
    big.write_bytes(b"\x89PNG" + b"\x00" * (31 * 1024 * 1024))  # 31 MB
    ref = MediaRef(raw=str(big), role=None, is_url=False)
    with pytest.raises(CliError) as ei:
        to_payload(ref, kind="image", model="2.0", budget=RequestBudget())
    assert ei.value.code == "INVALID_INPUT"
    assert "30" in ei.value.message  # mentions the 30 MB image limit


def test_heic_allowed_on_2_0_only():
    # We can't easily synthesize a real heic file; assert via the format-allowed
    # helper which is the canonical authority.
    assert format_allowed("heic", "image", "doubao-seedance-2-0-260128") is True
    assert format_allowed("heic", "image", "doubao-seedance-1-0-pro-250528") is False


def test_request_budget_overflow_raises():
    budget = RequestBudget()
    budget.bytes_used = MAX_REQUEST_BYTES - 100
    with pytest.raises(CliError) as ei:
        budget.add(200)
    assert ei.value.code == "INVALID_INPUT"
    assert "64" in ei.value.message  # mentions 64 MB request body cap
