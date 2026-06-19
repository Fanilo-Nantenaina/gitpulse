from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from gitpulse.web.server import app

client = TestClient(app)


def test_providers_endpoint():
    r = client.get("/api/providers")
    assert r.status_code == 200
    data = r.json()
    names = {p["name"] for p in data}
    assert {"claude", "openai", "gemini", "ollama"}.issubset(names)


def test_config_endpoint():
    r = client.get("/api/config")
    assert r.status_code == 200
    assert "languages" in r.json()


def test_index_served():
    r = client.get("/")
    assert r.status_code == 200
    assert "gitpulse" in r.text.lower()


def test_summary_endpoint(linear_repo):
    r = client.post(
        "/api/summary",
        json={"path": str(linear_repo), "when": "1000d", "provider": "local"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["activity"]["commit_count"] == 5
    assert "summary" in data


def test_log_endpoint(linear_repo):
    r = client.post("/api/log", json={"path": str(linear_repo), "when": "1000d"})
    assert r.status_code == 200
    assert r.json()["activity"]["commit_count"] == 5


def test_graph_endpoint(branched_repo):
    r = client.post("/api/graph", json={"path": str(branched_repo)})
    assert r.status_code == 200
    data = r.json()
    assert data["lanes"] >= 2
    assert data["nodes"]


def test_commit_message_endpoint(dirty_repo):
    r = client.post(
        "/api/commit-message",
        json={"path": str(dirty_repo), "scope": "all", "provider": "local"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["has_changes"] is True
    assert data["subject"]
    assert data["files"]


def test_commit_message_force_type(dirty_repo):
    r = client.post(
        "/api/commit-message",
        json={
            "path": str(dirty_repo),
            "scope": "all",
            "force_type": "feat",
            "provider": "local",
        },
    )
    assert r.json()["subject"].startswith("feat")


def test_changes_count_endpoint(dirty_repo):
    r = client.post("/api/changes-count", json={"path": str(dirty_repo)})
    assert r.status_code == 200
    data = r.json()
    assert data["count"] >= 3
    assert data["staged"] == 1


def test_changes_count_clean_repo(linear_repo):
    r = client.post("/api/changes-count", json={"path": str(linear_repo)})
    assert r.json()["count"] == 0


def test_compare_endpoint(branched_repo):
    r = client.post(
        "/api/compare", json={"path": str(branched_repo), "period": "7d", "periods": 2}
    )
    assert r.status_code == 200
    assert r.json()["metrics"]


def test_tracked_crud():
    # add
    r = client.post("/api/tracked", json={"url": "file:///tmp/x", "label": "x"})
    assert r.status_code == 200
    # list
    assert any(t["url"] == "file:///tmp/x" for t in client.get("/api/tracked").json())
    # remove
    r = client.request("DELETE", "/api/tracked", params={"needle": "file:///tmp/x"})
    assert r.json()["removed"] is True


def test_summary_bad_path_returns_400():
    r = client.post("/api/summary", json={"path": "/nonexistent/repo", "when": "7d"})
    assert r.status_code == 400
