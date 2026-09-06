from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from gitpulse.web.security import allowed_hostnames
from gitpulse.web.server import app

LOCAL = "http://127.0.0.1:8420"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, base_url=LOCAL)


@pytest.mark.parametrize(
    "host",
    ["attacker.com", "attacker.com:8420", "gitpulse.evil.test", "169.254.169.254"],
)
def test_foreign_host_header_is_rejected(client: TestClient, host: str) -> None:
    r = client.get("/api/config", headers={"Host": host})
    assert r.status_code == 421
    assert "Host" in r.json()["detail"]


@pytest.mark.parametrize(
    "host", ["127.0.0.1", "127.0.0.1:8420", "localhost", "localhost:8420", "[::1]:8420"]
)
def test_loopback_host_header_is_accepted(client: TestClient, host: str) -> None:
    assert client.get("/api/config", headers={"Host": host}).status_code == 200


def test_operator_can_allow_an_extra_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITPULSE_ALLOWED_HOSTS", "gitpulse.lan, box.local")
    assert "gitpulse.lan" in allowed_hostnames()
    assert "box.local" in allowed_hostnames()


def test_bind_host_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITPULSE_ALLOWED_HOSTS", raising=False)
    assert "192.168.1.50" in allowed_hostnames("192.168.1.50")
    assert "192.168.1.50" not in allowed_hostnames()


def test_cross_origin_write_is_rejected(client: TestClient) -> None:
    r = client.post(
        "/api/keys",
        json={"provider": "claude", "key": "sk-attacker"},
        headers={"Origin": "https://evil.test"},
    )
    assert r.status_code == 403


def test_cross_origin_read_is_rejected(client: TestClient) -> None:
    r = client.get("/api/browse", headers={"Origin": "https://evil.test"})
    assert r.status_code == 403


def test_opaque_origin_is_rejected(client: TestClient) -> None:
    r = client.get("/api/config", headers={"Origin": "null"})
    assert r.status_code == 403


def test_cross_site_fetch_metadata_is_rejected(client: TestClient) -> None:
    r = client.post(
        "/api/config/lang",
        json={"lang": "fr"},
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert r.status_code == 403


def test_same_origin_page_request_is_allowed(client: TestClient) -> None:
    r = client.post(
        "/api/config/lang",
        json={"lang": "fr"},
        headers={"Origin": LOCAL, "Sec-Fetch-Site": "same-origin"},
    )
    assert r.status_code == 200


def test_originless_local_client_is_allowed(client: TestClient) -> None:
    assert client.get("/api/config").status_code == 200


def test_index_is_still_served(client: TestClient) -> None:
    assert client.get("/").status_code == 200
