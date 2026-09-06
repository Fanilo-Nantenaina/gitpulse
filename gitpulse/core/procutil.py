from __future__ import annotations

import subprocess
import sys
from collections.abc import Mapping, Sequence
from typing import IO, Literal, overload

_NO_WINDOW: int = (
    getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    if sys.platform == "win32"
    else 0
)


@overload
def run(
    args: Sequence[str],
    *,
    capture_output: bool = ...,
    text: Literal[True],
    timeout: float | None = ...,
    env: Mapping[str, str] | None = ...,
) -> subprocess.CompletedProcess[str]: ...


@overload
def run(
    args: Sequence[str],
    *,
    capture_output: bool = ...,
    text: Literal[False] = ...,
    timeout: float | None = ...,
    env: Mapping[str, str] | None = ...,
) -> subprocess.CompletedProcess[bytes]: ...


def run(
    args: Sequence[str],
    *,
    capture_output: bool = False,
    text: bool = False,
    timeout: float | None = None,
    env: Mapping[str, str] | None = None,
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    if sys.platform == "win32":
        return subprocess.run(
            args,
            capture_output=capture_output,
            text=text,
            timeout=timeout,
            env=env,
            creationflags=_NO_WINDOW,
            startupinfo=_startupinfo(),
        )
    return subprocess.run(
        args,
        capture_output=capture_output,
        text=text,
        timeout=timeout,
        env=env,
    )


def popen(
    args: Sequence[str],
    *,
    stdout: int | IO[bytes] | None = None,
    stderr: int | IO[bytes] | None = None,
) -> subprocess.Popen[bytes]:
    if sys.platform == "win32":
        return subprocess.Popen(
            args, stdout=stdout, stderr=stderr, creationflags=_NO_WINDOW
        )
    return subprocess.Popen(args, stdout=stdout, stderr=stderr)


if sys.platform == "win32":

    def _startupinfo() -> subprocess.STARTUPINFO:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
        return si
