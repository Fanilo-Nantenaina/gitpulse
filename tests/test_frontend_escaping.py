
from __future__ import annotations

import re
from pathlib import Path

import pytest

from gitpulse import web

JS_DIR = Path(web.__file__).parent / "static" / "js"
JS_FILES = sorted(JS_DIR.glob("*.js"))


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def test_js_files_found():
    assert JS_FILES, f"no JS under {JS_DIR}"


def test_esc_escapes_quotes_as_well_as_angle_brackets():
    src = _read(JS_DIR / "core.js")
    assert "function esc(" in src, "esc() must be defined in core.js (loaded first)"
    table = re.search(r"const _ESC = \{(.+?)\};", src, re.S)
    assert table, "expected the _ESC lookup table in core.js"
    body = table.group(1)
    for char, entity in (
        ("&", "&amp;"),
        ("<", "&lt;"),
        (">", "&gt;"),
        ('"', "&quot;"),
        ("'", "&#39;"),
    ):
        assert entity in body, f"esc() does not escape {char!r} -> {entity}"


def test_esc_is_defined_only_once():
    defs = [p.name for p in JS_FILES if re.search(r"function esc\s*\(", _read(p))]
    assert defs == ["core.js"], f"esc() defined in {defs}"


def test_esc_is_defined_before_any_file_that_uses_it():
    index = (JS_DIR.parent / "index.html").read_text(encoding="utf-8")
    order = re.findall(r"/static/js/([\w.]+\.js)", index)
    assert order[0] == "core.js", f"core.js must load first, got {order}"


@pytest.mark.parametrize("path", JS_FILES, ids=lambda p: p.name)
def test_no_weak_three_char_escape_reappears(path):
    assert "/[&<>]/g" not in _read(path)


@pytest.mark.parametrize("path", JS_FILES, ids=lambda p: p.name)
def test_server_error_text_is_escaped_before_injection(path):
    assert "(e.message || e)" not in _read(path), (
        "raw error interpolation - wrap it in esc()"
    )


@pytest.mark.parametrize("path", JS_FILES, ids=lambda p: p.name)
def test_no_unescaped_title_attribute(path):
    for i, line in enumerate(_read(path).splitlines(), 1):
        for m in re.finditer(r"""title="'\s*\+\s*([^+]+?)\s*\+\s*'""", line):
            expr = m.group(1).strip()
            assert expr.startswith("esc(") or expr.startswith("t("), (
                f"{path.name}:{i}: unescaped title attribute: {expr}"
            )
