from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import pygit2


def cache_dir() -> Path:
    base = os.environ.get("GITPULSE_CACHE_DIR")
    if base:
        return Path(base)
    return Path.home() / ".gitpulse" / "remotes"


def repo_name_from_url(url: str) -> str:
    cleaned = url.rstrip("/")
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    tail = re.split(r"[/:]", cleaned)[-1]
    return tail or "repo"


def _cache_path(url: str) -> Path:
    digest = hashlib.sha1(url.encode()).hexdigest()[:12]
    return cache_dir() / f"{repo_name_from_url(url)}-{digest}.git"


def _inject_token(url: str, token: str, username: str | None) -> str:
    parts = urlparse(url)
    if parts.scheme not in ("http", "https"):
        return url
    user = username or "git"
    netloc = f"{user}:{token}@{parts.hostname}"
    if parts.port:
        netloc += f":{parts.port}"
    return urlunparse((parts.scheme, netloc, parts.path, "", "", ""))


def _is_ssh(url: str) -> bool:
    return url.startswith("git@") or url.startswith("ssh://")


def _callbacks(url: str, token: str | None, username: str | None,
               ssh_key: str | None) -> pygit2.RemoteCallbacks | None:
    if _is_ssh(url):
        user = "git"
        m = re.match(r"(?:ssh://)?([^@]+)@", url)
        if m:
            user = m.group(1)
        if ssh_key:
            pub = ssh_key + ".pub"
            passphrase = os.environ.get("GITPULSE_SSH_PASSPHRASE", "")
            cred = pygit2.Keypair(user, pub, ssh_key, passphrase)
        else:
            try:
                cred = pygit2.KeypairFromAgent(user)
            except Exception:
                return None
        return pygit2.RemoteCallbacks(credentials=cred)
    if token:
        return pygit2.RemoteCallbacks(
            credentials=pygit2.UserPass(username or "git", token))
    return None


def _clone_pygit2(url: str, dest: Path, token, username, ssh_key) -> bool:
    try:
        cb = _callbacks(url, token, username, ssh_key)
        pygit2.clone_repository(url, str(dest), bare=True, callbacks=cb)
        return True
    except Exception:
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        return False


def _run_git(args: list[str], env: dict | None = None) -> tuple[bool, str]:
    try:
        proc = subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=600,
            env={**os.environ, **(env or {})})
        return proc.returncode == 0, (proc.stderr or proc.stdout)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return False, str(e)


def _git_ssl_opts(insecure: bool) -> list[str]:
    return ["-c", "http.sslVerify=false"] if insecure else []


def _clone_cli(url: str, dest: Path, token, username, insecure: bool = False) -> tuple[bool, str]:
    clone_url = url
    env = {"GIT_TERMINAL_PROMPT": "0"}
    if token and not _is_ssh(url):
        clone_url = _inject_token(url, token, username)
    args = _git_ssl_opts(insecure) + ["clone", "--bare", "--quiet", clone_url, str(dest)]
    return _run_git(args, env)


def _fetch_cli(dest: Path, url: str, token, username, insecure: bool = False) -> tuple[bool, str]:
    env = {"GIT_TERMINAL_PROMPT": "0"}
    fetch_url = url
    if token and not _is_ssh(url):
        fetch_url = _inject_token(url, token, username)
    args = (_git_ssl_opts(insecure) +
            ["-C", str(dest), "fetch", "--quiet", fetch_url, "+refs/heads/*:refs/heads/*"])
    return _run_git(args, env)


def _is_valid_repo(dest: Path) -> bool:
    if not dest.exists():
        return False
    try:
        return pygit2.discover_repository(str(dest)) is not None
    except Exception:
        return False


def sync_remote(url: str, token: str | None = None, username: str | None = None,
                ssh_key: str | None = None, refresh: bool = True,
                insecure: bool = False) -> Path:
    dest = _cache_path(url)
    dest.parent.mkdir(parents=True, exist_ok=True)

    valid = _is_valid_repo(dest)

    if valid and not refresh:
        return dest

    if valid and refresh:
        ok, _ = _fetch_cli(dest, url, token, username, insecure)
        if ok:
            return dest
        shutil.rmtree(dest, ignore_errors=True)

    # Any leftover (partial/invalid) directory must be removed before cloning,
    # otherwise git refuses with "destination path already exists".
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)

    # pygit2 can't disable SSL verification, so when insecure is requested we
    # go straight to the git CLI which supports http.sslVerify=false.
    if not insecure and _clone_pygit2(url, dest, token, username, ssh_key):
        return dest

    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)

    ok, msg = _clone_cli(url, dest, token, username, insecure)
    if ok:
        return dest

    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)

    hint = ("For private repos set GITPULSE_GIT_TOKEN (HTTPS) or use an SSH URL "
            "with your key/agent configured.")
    if "CERT" in msg.upper() or "sslVerify" in msg or "SEC_E_CERT" in msg:
        hint = ("The server's SSL certificate failed verification (often expired). "
                "Fix the certificate server-side, or — at your own risk — enable "
                "the 'Allow insecure SSL' option for this repo.")
    raise RuntimeError(
        f"Could not clone {url}.\ngit said: {msg.strip()[:400]}\n{hint}")


def resolve_auth(token: str | None, username: str | None,
                 ssh_key: str | None) -> tuple[str | None, str | None, str | None]:
    token = token or os.environ.get("GITPULSE_GIT_TOKEN")
    username = username or os.environ.get("GITPULSE_GIT_USERNAME")
    ssh_key = ssh_key or os.environ.get("GITPULSE_SSH_KEY")
    return token, username, ssh_key


def clear_cache() -> int:
    d = cache_dir()
    if not d.exists():
        return 0
    n = sum(1 for _ in d.iterdir())
    shutil.rmtree(d, ignore_errors=True)
    return n
