# src/seedance_cli/framework/errors.py
from __future__ import annotations

from typing import Any

import httpx

from seedance_cli.framework.envelope import Failure

EXIT_CODES: dict[str, int] = {
    "INVALID_INPUT": 2,
    "CONFIG_MISSING": 2,
    "IO_ERROR": 3,
    "ARK_API_ERROR": 4,
    "NETWORK_ERROR": 5,
    "TASK_FAILED": 6,
    "TASK_EXPIRED": 7,
    "POLL_TIMEOUT": 8,
    "POLL_CANCELLED": 9,
    "INTERNAL": 10,
}


class CliError(Exception):
    def __init__(self, code: str, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def to_envelope(self) -> Failure:
        return Failure(code=self.code, message=self.message, details=self.details)


def exit_code_for(code: str) -> int:
    return EXIT_CODES.get(code, EXIT_CODES["INTERNAL"])


def translate(exc: Exception) -> CliError:
    if isinstance(exc, CliError):
        return exc
    if isinstance(
        exc,
        (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout),
    ):
        return CliError("NETWORK_ERROR", str(exc) or exc.__class__.__name__)
    # Ark SDK exception — duck-typed to avoid hard import dependency in framework layer
    if exc.__class__.__name__ in {"ArkAPIError", "ArkException"}:
        details: dict[str, Any] = {}
        for attr in ("status_code", "code", "message", "request_id"):
            if hasattr(exc, attr):
                details[attr] = getattr(exc, attr)
        return CliError("ARK_API_ERROR", str(exc), details=details or None)
    if isinstance(exc, (OSError, PermissionError, FileNotFoundError)):
        return CliError("IO_ERROR", str(exc))
    return CliError("INTERNAL", str(exc) or exc.__class__.__name__)
