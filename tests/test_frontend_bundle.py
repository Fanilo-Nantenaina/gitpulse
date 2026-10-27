
from __future__ import annotations

import re
from pathlib import Path

import pytest

from gitpulse import web

STATIC = Path(web.__file__).parent / "static"
ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


def test_index_references_assets_that_exist() -> None:
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    refs = re.findall(r'/static/(assets/[^"\']+\.(?:js|css))', html)
    assert any(r.endswith(".js") for r in refs), html
    assert any(r.endswith(".css") for r in refs), html
    for r in refs:
        assert (STATIC / r).is_file(), f"index.html points at missing {r}"


def test_bundle_is_packaged() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"web/static/assets/*"' in pyproject


@pytest.mark.skipif(not FRONTEND.exists(), reason="frontend sources not present")
def test_sources_never_inject_raw_html() -> None:
    offenders = [
        str(p.relative_to(FRONTEND))
        for p in FRONTEND.rglob("*.svelte")
        if "{@html" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []
