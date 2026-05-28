# tests/unit/framework/test_errors.py
import httpx

from seedance_cli.framework.errors import CliError, exit_code_for, translate


def test_cli_error_to_envelope():
    err = CliError("INVALID_INPUT", "bad --ratio", details={"flag": "--ratio"})
    env = err.to_envelope()
    assert env.code == "INVALID_INPUT"
    assert env.message == "bad --ratio"
    assert env.details == {"flag": "--ratio"}


def test_exit_code_for_known_codes():
    assert exit_code_for("INVALID_INPUT") == 2
    assert exit_code_for("CONFIG_MISSING") == 2
    assert exit_code_for("IO_ERROR") == 3
    assert exit_code_for("ARK_API_ERROR") == 4
    assert exit_code_for("NETWORK_ERROR") == 5
    assert exit_code_for("TASK_FAILED") == 6
    assert exit_code_for("TASK_EXPIRED") == 7
    assert exit_code_for("POLL_TIMEOUT") == 8
    assert exit_code_for("POLL_CANCELLED") == 9
    assert exit_code_for("INTERNAL") == 10


def test_exit_code_for_unknown_falls_back_to_internal():
    assert exit_code_for("MYSTERY") == 10


def test_translate_passes_cli_error_through():
    src = CliError("INVALID_INPUT", "x")
    assert translate(src) is src


def test_translate_oserror_to_io_error():
    err = translate(PermissionError("no perms"))
    assert err.code == "IO_ERROR"
    assert "no perms" in err.message


def test_translate_httpx_connect_to_network_error():
    err = translate(httpx.ConnectError("connection refused"))
    assert err.code == "NETWORK_ERROR"


def test_translate_httpx_timeout_to_network_error():
    err = translate(httpx.ReadTimeout("timed out"))
    assert err.code == "NETWORK_ERROR"


def test_translate_unknown_to_internal():
    err = translate(RuntimeError("???"))
    assert err.code == "INTERNAL"
    assert "???" in err.message


def test_translate_httpx_connect_timeout_to_network_error():
    err = translate(httpx.ConnectTimeout("connect timed out"))
    assert err.code == "NETWORK_ERROR"


def test_translate_ark_api_error_collects_details():
    class ArkAPIError(Exception):
        def __init__(self, msg: str) -> None:
            super().__init__(msg)
            self.status_code = 429
            self.code = "RateLimitExceeded"
            self.message = "too many requests"
            self.request_id = "req-abc"

    err = translate(ArkAPIError("rate limited"))
    assert err.code == "ARK_API_ERROR"
    assert err.details == {
        "status_code": 429,
        "code": "RateLimitExceeded",
        "message": "too many requests",
        "request_id": "req-abc",
    }


def test_translate_ark_subclass_is_caught():
    class ArkAPIError(Exception):
        pass

    class ArkRateLimitError(ArkAPIError):
        pass

    err = translate(ArkRateLimitError("limited"))
    assert err.code == "ARK_API_ERROR"
