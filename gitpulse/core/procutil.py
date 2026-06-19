from __future__ import annotations

import os
import subprocess

# Flags that suppress a new console window on Windows; no-op elsewhere.
_NO_WINDOW = 0
if os.name == "nt":
    _NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def run(args, **kwargs):
    """subprocess.run with the no-window flag applied on Windows."""
    if os.name == "nt":
        kwargs.setdefault("creationflags", 0)
        kwargs["creationflags"] |= _NO_WINDOW
        kwargs.setdefault("startupinfo", _startupinfo())
    return subprocess.run(args, **kwargs)


def popen(args, **kwargs):
    """subprocess.Popen with the no-window flag applied on Windows."""
    if os.name == "nt":
        kwargs.setdefault("creationflags", 0)
        kwargs["creationflags"] |= _NO_WINDOW
    return subprocess.Popen(args, **kwargs)


def _startupinfo():
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE
    return si
