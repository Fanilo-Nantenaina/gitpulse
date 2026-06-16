# GitPulse

AI-powered git activity digests. Turns your recent commit history into a
**narrative, theme-grouped summary** instead of a raw `git log` dump — with
multi-repo dashboards, scheduled reports, conventional-commits changelogs, and
work-pattern detection (hotspots, off-hours commits, productivity heatmaps).

## Why it's different

Most git-stat tools count commits. GitPulse _reads_ them: it sends commit
messages + per-file diffs to Claude, which clusters them into themes and writes
a human digest. The collection layer (pygit2) is just the boring part — the
value is the semantic layer on top.

## Install

```bash
pip install -e ".[all]"     # core + AI + scheduler + desktop notifications
export ANTHROPIC_API_KEY=sk-...   # enables Claude summaries (else local fallback)
```

Without an API key it still works: it falls back to a deterministic summary
(prefix grouping + pattern detection), so it's useful offline.

## Usage

```bash
gitpulse summary                      # last 7 days, current repo, terminal
gitpulse summary ~/proj --since 24h   # custom repo + window
gitpulse dashboard ~/code --since 30d # all repos under a dir, ranked
gitpulse changelog --from v1.2.0      # release notes (Conventional Commits)
gitpulse digest --to slack --to email # send digest to channels
gitpulse watch --every 24h --to slack # recurring scheduled digest
```

## Architecture

```
gitpulse/
├── core/
│   ├── models.py       # plain dataclasses: Commit, FileChange, RepoActivity
│   ├── collector.py    # pygit2 history walk + per-file diff stats
│   └── changelog.py    # Conventional-Commits release notes
├── ai/
│   └── summarizer.py   # Claude semantic summary + local fallback
├── cli/
│   ├── main.py         # Typer commands
│   └── render.py       # Rich terminal + Markdown output
├── scheduler/
│   └── runner.py       # APScheduler + systemd-timer unit generation
└── notifiers/
    └── dispatch.py     # slack / telegram / email / desktop
```

The core layer has **zero AI/CLI dependencies** — you can `import` the collector
in any other tool. The AI and notifier layers are optional extras.

## Configuration (env vars)

| Var                                                                  | Purpose                                      |
| -------------------------------------------------------------------- | -------------------------------------------- |
| `ANTHROPIC_API_KEY`                                                  | Enables Claude summaries                     |
| `GITPULSE_MODEL`                                                     | Override model (default `claude-sonnet-4-6`) |
| `GITPULSE_SLACK_WEBHOOK`                                             | Slack incoming webhook URL                   |
| `GITPULSE_TELEGRAM_TOKEN` / `_CHAT_ID`                               | Telegram bot                                 |
| `GITPULSE_SMTP_HOST` / `_PORT` / `_USER` / `_PASS` / `_TO` / `_FROM` | Email                                        |

## Roadmap (phase 2)

- **GUI**: Tauri (Rust shell + React) desktop app, or `gitpulse serve`
  (FastAPI + local web dashboard). The core/ai layers are already
  GUI-agnostic — the frontend just renders `RepoActivity` + `Summary`.
- **Git API**: pull remote repos for the multi-repo dashboard
  without local clones.
- **Standup mode**: "yesterday / today" generated from branch + WIP state.
- **Trend comparison**: this week vs. the rolling 4-week average.
- **Quality-risk flags**: large unreviewed diffs, commits without test changes.

## License

MIT
