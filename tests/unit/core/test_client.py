# tests/unit/core/test_client.py
import pytest

from seedance_cli.core.client import (
    DEFAULT_ENDPOINT,
    DEFAULT_MODEL,
    MODEL_ALIASES,
    expand_model,
    resolve_auth,
)
from seedance_cli.framework.errors import CliError


def test_expand_known_alias():
    assert expand_model("2.0") == "doubao-seedance-2-0-260128"
    assert expand_model("2.0-fast") == "doubao-seedance-2-0-fast-260128"
    assert expand_model("1.5-pro") == "doubao-seedance-1-5-pro-251215"
    assert expand_model("1.0-pro") == "doubao-seedance-1-0-pro-250528"
    assert expand_model("1.0-pro-fast") == "doubao-seedance-1-0-pro-fast-251015"


def test_expand_full_id_passes_through():
    assert expand_model("doubao-seedance-2-0-260128") == "doubao-seedance-2-0-260128"


def test_expand_unknown_short_alias_raises():
    with pytest.raises(CliError) as ei:
        expand_model("3.0")
    assert ei.value.code == "INVALID_INPUT"


def test_resolve_auth_flag_wins():
    api_key, endpoint = resolve_auth(
        cli_api_key="flag-key",
        cli_endpoint=None,
        env={"ARK_API_KEY": "env-key"},
        profile_api_key="profile-key",
        profile_endpoint="profile-endpoint",
    )
    assert api_key == "flag-key"
    assert endpoint == "profile-endpoint"


def test_resolve_auth_env_beats_profile():
    api_key, endpoint = resolve_auth(
        cli_api_key=None,
        cli_endpoint=None,
        env={"ARK_API_KEY": "env-key", "SEEDANCE_ENDPOINT": "env-endpoint"},
        profile_api_key="profile-key",
        profile_endpoint="profile-endpoint",
    )
    assert api_key == "env-key"
    assert endpoint == "env-endpoint"


def test_resolve_auth_profile_used_when_no_flag_or_env():
    api_key, endpoint = resolve_auth(
        cli_api_key=None,
        cli_endpoint=None,
        env={},
        profile_api_key="profile-key",
        profile_endpoint="profile-endpoint",
    )
    assert api_key == "profile-key"
    assert endpoint == "profile-endpoint"


def test_resolve_auth_missing_key_raises_config_missing():
    with pytest.raises(CliError) as ei:
        resolve_auth(
            cli_api_key=None,
            cli_endpoint=None,
            env={},
            profile_api_key=None,
            profile_endpoint=None,
        )
    assert ei.value.code == "CONFIG_MISSING"


def test_resolve_auth_endpoint_falls_back_to_default():
    _, endpoint = resolve_auth(
        cli_api_key="k",
        cli_endpoint=None,
        env={},
        profile_api_key=None,
        profile_endpoint=None,
    )
    assert endpoint == DEFAULT_ENDPOINT


def test_default_model_constant():
    assert DEFAULT_MODEL in MODEL_ALIASES.values()


def test_expand_forward_compat_passes_through_unknown_doubao_seedance_id():
    # Future model IDs we don't yet know about should pass through unchanged.
    assert expand_model("doubao-seedance-9-9-999999") == "doubao-seedance-9-9-999999"


def test_expand_doubao_prefix_but_not_seedance_raises():
    # The forward-compat rule is narrow: only `doubao-seedance-` prefix is trusted.
    with pytest.raises(CliError):
        expand_model("doubao-other-model-001")


def test_resolve_auth_cli_endpoint_wins_over_env_and_profile():
    _api_key, endpoint = resolve_auth(
        cli_api_key="k",
        cli_endpoint="https://flag-endpoint.example.com/api/v3",
        env={"SEEDANCE_ENDPOINT": "https://env-endpoint.example.com/api/v3"},
        profile_api_key=None,
        profile_endpoint="https://profile-endpoint.example.com/api/v3",
    )
    assert endpoint == "https://flag-endpoint.example.com/api/v3"


def test_make_ark_client_uses_args(monkeypatch):
    # Substitute the SDK's Ark class with a fake to verify make_ark_client
    # passes api_key and base_url through correctly.
    from seedance_cli.core import client as client_module

    captured = {}

    class FakeArk:
        def __init__(self, api_key: str, base_url: str) -> None:
            captured["api_key"] = api_key
            captured["base_url"] = base_url

        content_generation = None

    # Build a fake `volcenginesdkarkruntime` module containing FakeArk and
    # inject it into sys.modules so the lazy import inside make_ark_client
    # picks it up.
    import sys
    import types

    fake_module = types.ModuleType("volcenginesdkarkruntime")
    fake_module.Ark = FakeArk  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "volcenginesdkarkruntime", fake_module)

    result = client_module.make_ark_client("sk-test-key", "https://example.com/api/v3")
    assert isinstance(result, FakeArk)
    assert captured == {"api_key": "sk-test-key", "base_url": "https://example.com/api/v3"}
