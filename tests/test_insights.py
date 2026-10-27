from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from gitpulse.cli import main as cli_main
from gitpulse.core import doctor, risks, timesheet
from gitpulse.core.collector import collect_activity
from gitpulse.core.models import Commit, FileChange, RepoActivity
from gitpulse.web.server import app

MakeRepo = Callable[..., Path]
SINCE = datetime(2026, 1, 1, tzinfo=timezone.utc)
UNTIL = datetime(2026, 12, 31, tzinfo=timezone.utc)
runner = CliRunner()
client = TestClient(app, base_url="http://127.0.0.1:8420")
WIDE = {"COLUMNS": "200"}


def _commit(
    sha: str,
    when: str,
    summary: str = "feat: x",
    files: list[FileChange] | None = None,
    author: str = "Alice",
    repo: str = "",
) -> Commit:
    return Commit(
        sha=sha * 8,
        author_name=author,
        author_email=f"{author.lower()}@example.com",
        when=datetime.fromisoformat(when),
        summary=summary,
        body="",
        files=files or [FileChange("a.py", 1, 0, "modified")],
        repo=repo,
    )


def _activity(commits: list[Commit]) -> RepoActivity:
    return RepoActivity("proj", "", SINCE, UNTIL, commits)


def _kinds(found: list[risks.Risk]) -> list[str]:
    return [r["kind"] for r in found]


def test_committed_secret_is_flagged_from_the_diff(make_repo: MakeRepo) -> None:
    repo = make_repo(
        "leaky",
        [
            ("feat: base", "2026-03-01T10:00:00", {"app.py": "x = 1\n"}),
            (
                "feat: aws",
                "2026-03-02T10:00:00",
                {"conf/aws.py": 'KEY = "AKIAIOSFODNN7EXAMPLE"\n'},
            ),
        ],
    )
    found = risks.detect(collect_activity(repo, SINCE, UNTIL))
    assert _kinds(found)[0] == "committed_secret"
    top = found[0]
    assert top["severity"] == "high"
    assert "aws-access-key" in top["detail"] and "conf/aws.py" in top["detail"]
    assert "AKIAIOSFODNN7EXAMPLE" not in top["detail"]


def test_removed_secret_is_not_flagged(make_repo: MakeRepo) -> None:
    repo = make_repo(
        "cleaned",
        [
            (
                "feat: aws",
                "2026-03-01T10:00:00",
                {"k.py": 'KEY = "AKIAIOSFODNN7EXAMPLE"\n'},
            ),
            ("fix: drop key", "2026-03-02T10:00:00", {"k.py": "KEY = None\n"}),
        ],
    )
    activity = collect_activity(repo, datetime(2026, 3, 2, tzinfo=timezone.utc), UNTIL)
    assert "committed_secret" not in _kinds(risks.detect(activity))


def test_large_change_without_tests_versus_with_tests() -> None:
    big = [FileChange("src/core.py", 500, 20, "modified")]
    with_tests = [*big, FileChange("tests/test_core.py", 40, 0, "modified")]
    found = risks.detect(
        _activity(
            [
                _commit("a", "2026-03-01T10:00:00", "feat: engine", big),
                _commit("b", "2026-03-02T10:00:00", "feat: engine 2", with_tests),
            ]
        ),
        scan_secrets=False,
    )
    untested = [r for r in found if r["kind"] == "large_untested"]
    assert len(untested) == 1
    assert untested[0]["commits"] == ["a" * 8]


def test_lockfile_churn_is_not_a_huge_commit() -> None:
    lock = [FileChange("package-lock.json", 5000, 4000, "modified")]
    found = risks.detect(
        _activity([_commit("a", "2026-03-01T10:00:00", "chore: deps", lock)]),
        scan_secrets=False,
    )
    assert "huge_commit" not in _kinds(found)


def test_reverts_fix_chains_and_off_hours() -> None:
    f = [FileChange("api/auth.py", 3, 1, "modified")]
    commits = [
        _commit("a", "2026-03-01T23:00:00", "fix: login", f),
        _commit("b", "2026-03-02T23:30:00", "fix: login again", f),
        _commit("c", "2026-03-03T02:00:00", "fix: login for real", f),
        _commit("d", "2026-03-04T10:00:00", 'Revert "feat: sso"'),
        _commit("e", "2026-03-05T23:10:00", "feat: other"),
    ]
    kinds = _kinds(risks.detect(_activity(commits), scan_secrets=False))
    assert {"revert", "fix_chain", "off_hours"} <= set(kinds)
    assert kinds.index("fix_chain") < kinds.index("off_hours")


def test_quiet_window_has_no_flags(linear_repo: Path) -> None:
    assert risks.detect(collect_activity(linear_repo, SINCE, UNTIL)) == []


def test_hotspot_needs_other_files_to_stand_out() -> None:
    hot = FileChange("core/engine.py", 5, 2, "modified")
    commits = [
        _commit(
            c,
            f"2026-03-0{i + 1}T10:00:00",
            files=[hot, FileChange(f"f{i}.py", 1, 0, "added")],
        )
        for i, c in enumerate("abcde")
    ]
    found = risks.detect(_activity(commits), scan_secrets=False)
    assert [r["detail"] for r in found if r["kind"] == "churn_hotspot"] == [
        "core/engine.py changed in 5 of 5 commits."
    ]


def test_test_path_detection() -> None:
    for p in (
        "tests/test_x.py",
        "src/foo_test.go",
        "web/app.spec.ts",
        "a/__tests__/b.js",
        "FooTests.cs",
    ):
        assert risks.is_test_path(p), p
    for p in ("src/latest.py", "contest/main.py"):
        assert not risks.is_test_path(p), p


def test_sessions_split_on_gaps_and_add_warmup() -> None:
    commits = [
        _commit("a", "2026-03-02T09:00:00+00:00"),
        _commit("b", "2026-03-02T10:30:00+00:00"),
        _commit("c", "2026-03-02T16:00:00+00:00"),
    ]
    found = timesheet.sessions(_activity(commits), gap_minutes=120, warmup_minutes=30)
    assert [s.minutes for s in found] == [120, 30]
    report = timesheet.report(_activity(commits), 120, 30)
    assert report.total_minutes == 150
    assert report.days == 1
    assert timesheet.format_hours(report.total_minutes) == "2h30"


def test_sessions_are_per_author_and_split_across_repos() -> None:
    commits = [
        _commit("a", "2026-03-02T09:00:00+00:00", repo="api"),
        _commit("b", "2026-03-02T10:00:00+00:00", repo="web"),
        _commit("c", "2026-03-02T09:30:00+00:00", author="Bob", repo="api"),
    ]
    report = timesheet.report(_activity(commits), 120, 0)
    by_author = {n: m for n, m, _ in report.by("author")}
    assert by_author == {"Alice": 60, "Bob": 0}
    by_repo = {n: m for n, m, _ in report.by("repo")}
    assert by_repo == {"api": 30, "web": 30}


def test_time_report_exports() -> None:
    commits = [
        _commit("a", "2026-03-02T09:00:00+00:00"),
        _commit("b", "2026-03-02T09:45:00+00:00"),
    ]
    report = timesheet.report(_activity(commits))
    csv_text = report.to_csv()
    assert csv_text.splitlines()[0] == "day,author,repo,hours,minutes,commits,sessions"
    assert "2026-03-02,Alice,,1.25,75,2,1" in csv_text
    assert "| 2026-03-02 | Alice | - | 1.25 | 2 |" in report.to_markdown()


def test_doctor_runs_every_core_check() -> None:
    checks = doctor.run_all()
    names = {c["name"] for c in checks}
    assert {"python", "pygit2", "git CLI", "config dir", "caches", "web UI"} <= names
    assert all(c["status"] in ("ok", "warn", "fail") for c in checks)
    assert not [c for c in checks if c["status"] == "fail"]


def test_cli_timesheet_csv_and_table(make_repo: MakeRepo) -> None:
    repo = make_repo(
        "tt",
        [
            ("feat: a", "2026-03-02T09:00:00", {"a.py": "1"}),
            ("feat: b", "2026-03-02T10:00:00", {"a.py": "2"}),
        ],
    )
    res = runner.invoke(
        cli_main.app,
        ["timesheet", str(repo), "-w", "2026-03-01..2026-03-31", "-f", "csv"],
    )
    assert res.exit_code == 0, res.output
    assert res.output.splitlines()[1].endswith(",90,2,1")
    res = runner.invoke(
        cli_main.app, ["timesheet", str(repo), "-w", "2026-03-01..2026-03-31"], env=WIDE
    )
    assert "1h30" in res.output


def test_cli_risks_fail_on(make_repo: MakeRepo) -> None:
    repo = make_repo(
        "leaky",
        [
            (
                "feat: aws",
                "2026-03-02T10:00:00",
                {"k.py": 'KEY = "AKIAIOSFODNN7EXAMPLE"\n'},
            )
        ],
    )
    args = ["risks", str(repo), "-w", "2026-03-01..2026-03-31"]
    res = runner.invoke(cli_main.app, args, env=WIDE)
    assert res.exit_code == 0, res.output
    assert "Possible secret committed" in res.output
    assert runner.invoke(cli_main.app, [*args, "--fail-on", "high"]).exit_code == 2
    assert (
        runner.invoke(
            cli_main.app, [*args, "--no-secrets", "--fail-on", "high"]
        ).exit_code
        == 0
    )


def test_cli_summary_dry_run_sends_nothing(linear_repo: Path) -> None:
    res = runner.invoke(
        cli_main.app,
        ["summary", str(linear_repo), "-w", "1000d", "-p", "local", "--dry-run"],
        env=WIDE,
    )
    assert res.exit_code == 0, res.output
    assert "Dry run: nothing was sent." in res.output
    assert "local fallback (no model)" in res.output


def test_cli_history_and_doctor() -> None:
    res = runner.invoke(cli_main.app, ["history", "list"])
    assert "No saved digests yet" in res.output
    res = runner.invoke(cli_main.app, ["doctor"], env=WIDE)
    assert "GitPulse doctor" in res.output


def test_api_summary_includes_risks(linear_repo: Path) -> None:
    r = client.post(
        "/api/summary",
        json={"path": str(linear_repo), "when": "1000d", "provider": "local"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["risks"] == []
    assert data["summary"]["cached"] is False
    assert data["summary"]["redactions"] == 0


def test_api_timesheet_risks_history_doctor(linear_repo: Path) -> None:
    r = client.post(
        "/api/timesheet",
        json={"path": str(linear_repo), "when": "2026-01-01..2026-01-31"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["days"] == 5
    assert data["total_minutes"] == 5 * 30
    assert data["csv"].startswith("day,author")
    r = client.post("/api/risks", json={"path": str(linear_repo), "when": "1000d"})
    assert r.json()["risks"] == []
    assert client.get("/api/history").json() == {"entries": []}
    assert client.get("/api/doctor").json()["checks"]
