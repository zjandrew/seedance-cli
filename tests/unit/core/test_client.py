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
