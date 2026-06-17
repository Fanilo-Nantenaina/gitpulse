# GitPulse

**AI-powered git activity digests.** GitPulse turns your recent commit history
into a narrative, theme-grouped summary instead of a raw `git log` dump — with
multi-repo dashboards, scheduled reports, Conventional-Commits changelogs, and
work-pattern detection (hotspots, off-hours commits, productivity heatmaps).

---

## Why it's different

Most git-stat tools count commits. GitPulse _reads_ them: it sends commit
messages and per-file diff stats to Claude, which clusters them into themes and
writes a human digest. The collection layer (pygit2) is the boring part — the
value is the semantic layer on top.

Without an API key it still works: it falls back to a deterministic local
summary (prefix grouping + pattern detection), so it's useful offline too.

---

## Install

```bash
git clone https://github.com/Fanilo-Nantenaina/gitpulse.git
cd gitpulse
pip install -e ".[all]"      # core + AI + scheduler + desktop notifications
```

Editable install (`-e`) means changes to the source take effect immediately,
without reinstalling.

### Optional dependency groups

| Extra      | Pulls in         | Needed for                |
| ---------- | ---------------- | ------------------------- |
| `ai`       | `anthropic`      | Claude semantic summaries |
| `schedule` | `apscheduler`    | `gitpulse watch`          |
| `desktop`  | `plyer`          | desktop notifications     |
| `all`      | all of the above | everything                |

Install a subset, e.g. `pip install -e ".[ai]"`, if you don't need the rest.

> **Windows note:** `pygit2` ships prebuilt wheels for most Python versions.
> If `pip install` fails on it, upgrade pip (`python -m pip install -U pip`)
> and retry, or install a Python version with an available wheel.

---

## Configuration

GitPulse reads secrets from **environment variables** — there is no config
file by default, so no secret can be accidentally committed. Copy
`.env.example` to `.env` for reference, or set system variables directly.

### Persisting variables on Windows (PowerShell)

```powershell
[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")
```

Restart the terminal afterwards so the variable is picked up.

### All variables

| Variable                    | Purpose                                        | Default             |
| --------------------------- | ---------------------------------------------- | ------------------- |
| `ANTHROPIC_API_KEY`         | Enables Claude summaries (else local fallback) | —                   |
| `GITPULSE_MODEL`            | Model override                                 | `claude-sonnet-4-6` |
| `GITPULSE_SLACK_WEBHOOK`    | Slack incoming webhook URL                     | —                   |
| `GITPULSE_TELEGRAM_TOKEN`   | Telegram bot token (via @BotFather)            | —                   |
| `GITPULSE_TELEGRAM_CHAT_ID` | Telegram chat ID                               | —                   |
| `GITPULSE_SMTP_HOST`        | SMTP server host                               | —                   |
| `GITPULSE_SMTP_PORT`        | SMTP port                                      | `587`               |
| `GITPULSE_SMTP_USER`        | SMTP username                                  | —                   |
| `GITPULSE_SMTP_PASS`        | SMTP password (Gmail: app password)            | —                   |
| `GITPULSE_SMTP_TO`          | Recipient address                              | —                   |
| `GITPULSE_SMTP_FROM`        | Sender address                                 | falls back to `_TO` |

---

## Time windows (`--when`)

All activity commands take `--when` / `-w` (this replaces the old `--since`).
It accepts several formats:

| Type        | Example                                                   | Resolves to                            |
| ----------- | --------------------------------------------------------- | -------------------------------------- |
| interval    | `7d`, `24h`, `30m`                                        | rolling window ending now              |
| single date | `2026-06-15`                                              | that whole day (00:00-23:59)           |
| range       | `2026-06-10..2026-06-14`                                  | inclusive span                         |
| open range  | `2026-06-12..`                                            | from that date to now                  |
| relative    | `today`, `yesterday`, `avant-hier`                        | that whole day                         |
| weekday     | `thursday`, `jeudi`, `"jeudi dernier"`, `"last thursday"` | most recent occurrence of that weekday |
| week        | `this-week`, `last-week`                                  | Monday-Sunday span                     |

French and English terms are both accepted. Run `gitpulse dates` to print this
table plus the concrete dates for the current week (e.g. `thursday (last) ->
2026-06-11`).

```bash
gitpulse summary --when yesterday
gitpulse log --when 2026-06-10..2026-06-14
gitpulse summary --when "jeudi dernier"
```

---

## Commands

Run `gitpulse --help` for the index, or `gitpulse <command> --help` for any
single command.

### `gitpulse summary [PATH]`

Print an AI semantic summary of recent activity to the terminal: a headline,
themes grouping related commits, observations (hotspots, off-hours commits,
risk flags), a 24-hour productivity sparkline, and a cost line showing whether
the summary came from Claude or the local fallback plus token usage and cost.

| Option     | Alias | Default | Description                               |
| ---------- | ----- | ------- | ----------------------------------------- |
| `PATH`     |       | `.`     | Repository path (quote paths with spaces) |
| `--when`   | `-w`  | `7d`    | Time window (see above)                   |
| `--branch` | `-b`  | HEAD    | Specific branch to analyze                |

```bash
gitpulse summary
gitpulse summary "C:\path with spaces\repo" --when 24h
gitpulse summary ~/proj -b develop -w last-week
```

### `gitpulse log [PATH]`

Plain `git log`-style listing: one entry per commit with SHA, author, date,
message, and diff stats. No AI call, no cost. Use `--files` to list changed
files per commit.

| Option     | Alias | Default | Description                   |
| ---------- | ----- | ------- | ----------------------------- |
| `PATH`     |       | `.`     | Repository path               |
| `--when`   | `-w`  | `7d`    | Time window                   |
| `--branch` | `-b`  | HEAD    | Specific branch               |
| `--files`  | `-f`  | off     | List changed files per commit |

```bash
gitpulse log --when yesterday
gitpulse log ~/proj -w 2026-06-10..2026-06-14 --files
```

### `gitpulse digest [PATH]`

Generate the AI summary as Markdown and dispatch it to notification channels.

| Option   | Alias | Default   | Description         |
| -------- | ----- | --------- | ------------------- |
| `PATH`   |       | `.`       | Repository path     |
| `--when` | `-w`  | `7d`      | Time window         |
| `--to`   |       | `desktop` | Channel; repeatable |

```bash
gitpulse digest --to slack
gitpulse digest ~/proj --when 7d --to slack --to email
```

If no channel succeeds (e.g. none configured), the Markdown is printed to the
terminal as a fallback.

### `gitpulse dashboard [ROOT]`

Aggregated activity across every repo found under a directory, ranked by
commit count.

| Option    | Alias | Default | Description                 |
| --------- | ----- | ------- | --------------------------- |
| `ROOT`    |       | `.`     | Directory to scan for repos |
| `--when`  | `-w`  | `7d`    | Time window                 |
| `--depth` |       | `3`     | Max search depth for repos  |

```bash
gitpulse dashboard ~/code --when 30d
gitpulse dashboard "C:\Users\You\Documents" --depth 2
```

### `gitpulse changelog [PATH]`

Generate Conventional-Commits release notes between two refs, grouped by type
(features, fixes, perf, breaking changes, ...).

| Option   | Default | Description                                             |
| -------- | ------- | ------------------------------------------------------- |
| `PATH`   | `.`     | Repository path                                         |
| `--from` | none    | Starting ref (e.g. `v1.2.0`); omit to walk full history |
| `--to`   | `HEAD`  | Ending ref                                              |

```bash
gitpulse changelog --from v1.2.0
gitpulse changelog ~/proj --from v1.0.0 --to v1.1.0 > CHANGELOG.md
```

### `gitpulse watch [PATH]`

Run digests on a recurring schedule. Blocks the terminal (requires
`apscheduler`).

| Option    | Alias | Default   | Description                          |
| --------- | ----- | --------- | ------------------------------------ |
| `PATH`    |       | `.`       | Repository path                      |
| `--every` | `-e`  | `24h`     | Cadence between runs (interval only) |
| `--when`  | `-w`  | `24h`     | Window each digest covers            |
| `--to`    |       | `desktop` | Channel; repeatable                  |

```bash
gitpulse watch --every 24h --to slack
gitpulse watch ~/proj -e 7d --to email
```

### `gitpulse dates`

Print the accepted `--when` formats and the concrete dates for the current
week. Takes no options.

```bash
gitpulse dates
```

---

## Notifiers

Each channel activates only when its environment variables are set; otherwise
it is silently skipped. Configure them, then pass `--to <channel>` to `digest`
or `watch`.

| Channel    | Required variables                                           | Notes                                     |
| ---------- | ------------------------------------------------------------ | ----------------------------------------- |
| `desktop`  | none                                                         | Requires `plyer`. Native OS notification. |
| `slack`    | `GITPULSE_SLACK_WEBHOOK`                                     | Slack incoming webhook URL.               |
| `telegram` | `GITPULSE_TELEGRAM_TOKEN`, `GITPULSE_TELEGRAM_CHAT_ID`       | Bot via @BotFather.                       |
| `email`    | `GITPULSE_SMTP_HOST` + `_PORT`/`_USER`/`_PASS`/`_TO`/`_FROM` | Gmail needs an app password.              |

Add a channel by writing a `notify_*(markdown) -> bool` function in
`gitpulse/notifiers/dispatch.py` and registering it in the `NOTIFIERS` dict.

---

## Scheduling

Two approaches, by design:

**`gitpulse watch`** — convenient for testing or an always-on machine. Uses
APScheduler and blocks the terminal; closing it stops the schedule.

**OS-native scheduler** — the robust choice for production:

- **Linux (VPS):** `gitpulse/scheduler/runner.py` exposes
  `systemd_timer_unit(interval, command)`, which returns the `.service` and
  `.timer` unit text for a systemd timer. Drop them in `/etc/systemd/system/`,
  then `systemctl enable --now gitpulse.timer`.
- **Windows:** create a Task Scheduler entry that runs
  `gitpulse digest "C:\...\repo" --to slack` at the desired interval. More
  reliable than a long-running Python process.

---

## Cost & token usage

Each summary is a single API call. GitPulse sizes its output budget to the
number of commits (`max_tokens` scales from 2,000 to 8,000) so the JSON
response is never truncated on large repos. Every run prints a cost line:

```
claude · 6893+2400 tok · $0.0567
```

or, when no key is set:

```
local fallback (no API call, $0.00)
```

Pricing follows the model in use; check the Anthropic console for current
rates. Use a shorter `--when` window while testing to keep payloads small.

---

## Architecture

```
gitpulse/
├── core/
│   ├── models.py       # plain dataclasses: Commit, FileChange, RepoActivity
│   ├── collector.py    # pygit2 history walk + per-file diff stats
│   ├── dateparse.py    # --when parsing: intervals, dates, ranges, weekdays
│   └── changelog.py    # Conventional-Commits release notes
├── ai/
│   └── summarizer.py   # Claude semantic summary + local fallback + cost tracking
├── cli/
│   ├── main.py         # Typer commands
│   └── render.py       # Rich terminal, git-log view, Markdown output
├── scheduler/
│   └── runner.py       # APScheduler + systemd-timer unit generation
└── notifiers/
    └── dispatch.py     # slack / telegram / email / desktop
```

The `core` layer has zero AI/CLI dependencies — import the collector in any
other tool. The `ai` and `notifiers` layers are optional extras.

---

## Roadmap

- **GUI** — Tauri (Rust shell + React) desktop app, or `gitpulse serve`
  (FastAPI + local web dashboard). The core/ai layers are already
  GUI-agnostic; the frontend just renders `RepoActivity` + `Summary`.
- **Forgejo / GitHub API** — pull remote repos for the dashboard without
  local clones.
- **Standup mode** — "yesterday / today" generated from branch + WIP state.
- **Trend comparison** — this week vs. the rolling 4-week average.
- **Quality-risk flags** — large unreviewed diffs, commits without test changes.

---

## License

MIT — see [LICENSE](LICENSE).
