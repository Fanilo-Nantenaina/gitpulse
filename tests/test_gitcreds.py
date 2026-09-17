from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from unittest import mock

import pytest

from gitpulse.core import remote as R
from gitpulse.core.gitcreds import base64_basic, git_config_env, redact

TOKEN = "ghp_" + "A" * 36
URL = "https://github.com/acme/private.git"


class Captured:
    argv: list[str]
    env: dict[str, str]


@pytest.fixture
def captured() -> Iterator[Captured]:
    seen = Captured()

    def fake_run(
        args: Sequence[object],
        *,
        env: Mapping[str, str] | None = None,
        **kw: object,
    ) -> object:
        seen.argv = [str(a) for a in args]
        seen.env = dict(env or {})

        class Proc:
            returncode: int = 1
            stdout: str = ""
            stderr: str = (
                f"fatal: could not read from "
                f"https://x-access-token:{TOKEN}@github.com/acme/private.git/\n"
            )

        return Proc()

    with mock.patch("gitpulse.core.procutil.run", fake_run):
        yield seen


def test_clone_keeps_token_out_of_argv(captured: Captured) -> None:
    R._clone_cli(URL, Path("/tmp/x"), TOKEN, None)
    assert TOKEN not in " ".join(captured.argv)


def test_fetch_keeps_token_out_of_argv(captured: Captured) -> None:
    R._fetch_cli(Path("/tmp/x"), URL, TOKEN, None)
    assert TOKEN not in " ".join(captured.argv)


def test_clone_passes_credential_through_environment(captured: Captured) -> None:
    R._clone_cli(URL, Path("/tmp/x"), TOKEN, None)
    env = captured.env
    assert env["GIT_CONFIG_COUNT"] == "1"
    assert env["GIT_CONFIG_KEY_0"] == "http.extraHeader"
    assert env["GIT_CONFIG_VALUE_0"].startswith("Authorization: Basic ")
    assert env["GIT_TERMINAL_PROMPT"] == "0"


def test_userinfo_embedded_by_the_caller_is_stripped_from_argv(
    captured: Captured,
) -> None:
    R._clone_cli(
        f"https://user:{TOKEN}@github.com/acme/p.git", Path("/tmp/x"), None, None
    )
    argv = " ".join(captured.argv)
    assert TOKEN not in argv
    assert "https://github.com/acme/p.git" in argv


def test_git_stderr_is_redacted_before_return(captured: Captured) -> None:
    ok, msg = R._clone_cli(URL, Path("/tmp/x"), TOKEN, None)
    assert not ok
    assert TOKEN not in msg
    assert "***" in msg


def test_sync_remote_error_carries_no_credential(
    captured: Captured, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITPULSE_CACHE_DIR", str(tmp_path))

    def never_clones(*a: object, **k: object) -> bool:
        return False

    monkeypatch.setattr(R, "_clone_pygit2", never_clones)
    with pytest.raises(RuntimeError) as exc:
        R.sync_remote(URL, token=TOKEN)
    assert TOKEN not in str(exc.value)


@pytest.mark.parametrize(
    "raw",
    [
        "https://user:s3cr3tvalue@host/r.git",
        "sk-ant-api03-" + "A" * 40,
        "glpat-" + "B" * 24,
        "AIza" + "C" * 35,
        "ghp_" + "D" * 36,
        "github_pat_" + "E" * 30,
    ],
)
def test_known_secret_shapes_are_redacted(raw: str) -> None:
    assert "***" in redact(raw)


def test_basic_and_bearer_headers_are_redacted() -> None:
    header = "Authorization: Basic " + base64_basic("x-access-token", TOKEN)
    assert redact(header) == "Authorization: ***"
    assert redact("Authorization: Bearer sk-live-" + "F" * 30) == "Authorization: ***"


def test_supplied_secret_is_redacted_even_with_an_unknown_shape() -> None:
    weird = "not-a-recognised-token-shape-12345"
    assert weird not in redact(f"failed using {weird}", weird)


def test_redact_handles_empty_and_none() -> None:
    assert redact(None) == ""
    assert redact("") == ""


def test_short_secrets_are_not_used_as_replacement_patterns() -> None:
    assert redact("the cat sat", "cat") == "the cat sat"


@pytest.mark.parametrize("url", ["git@github.com:acme/p.git", "ssh://git@h/acme/p.git"])
def test_no_auth_header_for_ssh_urls(url: str) -> None:
    env = git_config_env(TOKEN, None, False, for_url=url)
    assert env["GIT_CONFIG_COUNT"] == "0"
    assert not any(k.startswith("GIT_CONFIG_KEY") for k in env)


def test_insecure_ssl_is_passed_as_config_not_argv() -> None:
    env = git_config_env(None, None, True, for_url=URL)
    keys = {env[k]: env[k.replace("KEY", "VALUE")] for k in env if "KEY_" in k}
    assert keys["http.sslVerify"] == "false"


def test_sync_remote_preserves_valid_cache_on_fetch_failure(
    linear_repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_dir = tmp_path / "remotes"
    cache_dir.mkdir()
    monkeypatch.setenv("GITPULSE_CACHE_DIR", str(cache_dir))

    url = "https://github.com/example/repo.git"
    cached_dest = R._cache_path(url)
    import shutil

    shutil.copytree(linear_repo, cached_dest)

    def fail_fetch(*a: object, **k: object) -> tuple[bool, str]:
        return False, "network unreachable"

    monkeypatch.setattr(R, "_fetch_cli", fail_fetch)

    result = R.sync_remote(url, refresh=True)
    assert result == cached_dest
    assert cached_dest.exists()

