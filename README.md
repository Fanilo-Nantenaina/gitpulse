# GitPulse

**AI-powered git activity digests.** GitPulse turns your recent commit history
into a narrative, theme-grouped summary instead of a raw `git log` dump — with
multi-repo dashboards, scheduled reports, Conventional-Commits changelogs, and
work-pattern detection (hotspots, off-hours commits, productivity heatmaps).

---

## Why it's different

Most git-stat tools count commits. GitPulse _reads_ them: it sends commit
messages, full bodies, per-file diff stats, and a precomputed signals block
(churn hotspots, off-hours commits, fix/revert chains, large diffs) to a
language model, which clusters the work into themes and writes a code-review-
style digest. The collection layer (pygit2) is the boring part — the value is
the semantic layer on top.

The digest aims for specificity: themes cite concrete files and symbols, and
observations are required to reference real evidence (a named file, a commit
sha, a count, a sequence) rather than generic advice like "may require
testing". The signals block gives the model hard facts to ground those
observations in.

The model can be Anthropic's Claude API or a local Ollama model — GitPulse
auto-detects what's available, or you pick one explicitly. With no model at all
it still works: it falls back to a deterministic local summary (prefix grouping

- pattern detection), so it's useful fully offline too.

A note on local models: smaller Ollama models follow the "be specific, cite
evidence" instructions less reliably than Claude or large coder models. For the
sharpest observations, prefer Claude or a large coder-tuned model
(e.g. qwen3-coder).

---

## Install

```bash
git clone https://github.com/<you>/gitpulse.git
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

| Variable                    | Purpose                                     | Default                  |
| --------------------------- | ------------------------------------------- | ------------------------ |
| `ANTHROPIC_API_KEY`         | Enables the Claude provider                 | —                        |
| `GITPULSE_MODEL`            | Claude model                                | `claude-sonnet-4-6`      |
| `GITPULSE_LANG`             | Default output language (code or name)      | `en`                     |
| `GITPULSE_GIT_TOKEN`        | Access token for private HTTPS remotes      | —                        |
| `GITPULSE_GIT_USERNAME`     | Username for token auth                     | `git`                    |
| `GITPULSE_SSH_KEY`          | Path to private SSH key for SSH remotes     | agent                    |
| `GITPULSE_SSH_PASSPHRASE`   | Passphrase for the SSH key, if any          | —                        |
| `GITPULSE_CACHE_DIR`        | Where remote clones are cached              | `~/.gitpulse/remotes`    |
| `OLLAMA_HOST`               | Ollama server URL                           | `http://localhost:11434` |
| `GITPULSE_OLLAMA_MODEL`     | Default Ollama model (else first installed) | —                        |
| `GITPULSE_SLACK_WEBHOOK`    | Slack incoming webhook URL                  | —                        |
| `GITPULSE_TELEGRAM_TOKEN`   | Telegram bot token (via @BotFather)         | —                        |
| `GITPULSE_TELEGRAM_CHAT_ID` | Telegram chat ID                            | —                        |
| `GITPULSE_SMTP_HOST`        | SMTP server host                            | —                        |
| `GITPULSE_SMTP_PORT`        | SMTP port                                   | `587`                    |
| `GITPULSE_SMTP_USER`        | SMTP username                               | —                        |
| `GITPULSE_SMTP_PASS`        | SMTP password (Gmail: app password)         | —                        |
| `GITPULSE_SMTP_TO`          | Recipient address                           | —                        |
| `GITPULSE_SMTP_FROM`        | Sender address                              | falls back to `_TO`      |

---

## AI providers

GitPulse can summarize with different backends, selected per command with
`--provider` / `-p` and optionally `--model` / `-m`.

| Provider         | Requires                                        | Cost                                                       |
| ---------------- | ----------------------------------------------- | ---------------------------------------------------------- |
| `claude`         | `ANTHROPIC_API_KEY` + `anthropic` package       | paid (per token)                                           |
| `ollama`         | a running Ollama server with at least one model | free, local, offline                                       |
| `local`          | nothing                                         | free; deterministic, no model                              |
| `auto` (default) | —                                               | picks the first available: claude, then ollama, then local |

Run `gitpulse providers` to see which backends are available and, for Ollama,
which models are installed:

```bash
gitpulse providers
```

### Using Ollama

Install Ollama, pull a model, and GitPulse finds it automatically:

```bash
ollama pull llama3.1            # or qwen2.5-coder, mistral, etc.
gitpulse summary -p ollama      # uses the first installed model
gitpulse summary -p ollama -m qwen2.5-coder:7b
```

If `--model` is omitted for Ollama, the first installed model is used. Set
`GITPULSE_OLLAMA_MODEL` to fix a default. A non-default server location can be
set with `OLLAMA_HOST`.

Coder-tuned models (qwen2.5-coder, deepseek-coder) tend to produce the best
commit summaries. Quality is lower than Claude but the run is free and offline.

### Forcing a provider

```bash
gitpulse summary -p claude -m claude-opus-4-8   # explicit Claude model
gitpulse summary -p local                        # skip models entirely
gitpulse summary                                 # auto
```

If a selected provider fails or returns malformed output, GitPulse degrades to
the local summary rather than erroring; the cost line reports what happened
(e.g. `local(ollama-parse-failed)`).

---

## Language

Summaries (headlines, theme titles, narratives, observations) can be written in
any supported language. Commit identifiers, file paths, code symbols, and branch
names are always left unchanged.

Supported codes: `en`, `fr`, `es`, `de`, `pt`, `it`, `mg`, `ar`, `zh`, `ja`.
Both the code (`fr`) and the English name (`French`) are accepted.

The language is resolved in this order, first match wins:

1. the `--lang` / `-l` option on the command
2. the `GITPULSE_LANG` environment variable
3. the saved default (set via `gitpulse config --lang`)
4. English

So you can set it once and forget it, or override per command:

```bash
gitpulse config --lang fr          # set the default to French, persisted
gitpulse summary                   # now in French
gitpulse summary --lang en         # this run in English, default unchanged
gitpulse config --show             # see the active language and where it comes from
```

The Claude provider honors the language directly. Ollama follows it too, though
smaller local models may be less reliable at it. The local fallback is
translated for `en` and `fr`; other languages fall back to English wording for
its fixed phrases (the AI providers are unaffected).

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

Options belong to a command, not to `gitpulse` itself. Write
`gitpulse summary --provider ollama`, not `gitpulse --provider ollama`.

### `gitpulse summary [PATH]`

Print an AI semantic summary of recent activity to the terminal: a headline,
themes grouping related commits, observations (hotspots, off-hours commits,
risk flags), a 24-hour productivity sparkline, and a cost line showing whether
the summary came from Claude or the local fallback plus token usage and cost.

| Option       | Alias | Default          | Description                               |
| ------------ | ----- | ---------------- | ----------------------------------------- |
| `PATH`       |       | `.`              | Repository path (quote paths with spaces) |
| `--when`     | `-w`  | `7d`             | Time window (see above)                   |
| `--branch`   | `-b`  | HEAD             | Specific branch to analyze                |
| `--provider` | `-p`  | `auto`           | AI backend: auto, claude, ollama, local   |
| `--model`    | `-m`  | provider default | Model name                                |
| `--lang`     | `-l`  | default          | Output language (code or name)            |

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

### `gitpulse remote <URL>`

Analyze a repository hosted anywhere, without cloning it yourself first. Works
with any git host — GitHub, GitLab, Forgejo/Gitea, Bitbucket, Codeberg, a
self-hosted git server — because it uses the standard git protocol, not any
host-specific API. The repo is cloned bare (history only, no working files)
into a local cache and refreshed on each run.

| Option                          | Alias | Default   | Description                             |
| ------------------------------- | ----- | --------- | --------------------------------------- |
| `URL`                           |       | required  | Git URL, HTTPS or SSH                   |
| `--when`                        | `-w`  | `7d`      | Time window                             |
| `--branch`                      | `-b`  | HEAD      | Specific branch                         |
| `--view`                        |       | `summary` | `summary` (AI) or `log` (plain listing) |
| `--files`                       | `-f`  | off       | In log view, list files per commit      |
| `--token`                       |       | env       | Access token for private HTTPS repos    |
| `--username`                    |       | `git`     | Username for token auth                 |
| `--ssh-key`                     |       | agent     | Path to a private SSH key               |
| `--no-refresh`                  |       | off       | Use the cached clone, skip fetching     |
| `--provider` `--model` `--lang` |       |           | Same as `summary`                       |

Authentication, two ways, both configurable:

- **HTTPS + token** — pass `--token`, or set `GITPULSE_GIT_TOKEN` (and
  optionally `GITPULSE_GIT_USERNAME`). The token is injected into the fetch URL
  and never written to disk.
- **SSH** — use an SSH URL (`git@host:org/repo.git`). GitPulse uses your SSH
  agent by default, or a specific key via `--ssh-key` / `GITPULSE_SSH_KEY`
  (passphrase via `GITPULSE_SSH_PASSPHRASE`).

```bash
gitpulse remote https://github.com/org/project.git -w last-week
gitpulse remote git@forgejo.example.com:team/project.git -w 7d
gitpulse remote https://gitlab.com/org/repo.git --token ghp_xxx -p ollama
gitpulse remote https://codeberg.org/user/app.git --view log --files
```

Under the hood it tries pygit2 first and falls back to the system `git`
command, so SSH and HTTPS work even where pygit2 lacks transport support.
Clear the cache with `gitpulse cache-clear`.

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

| Option       | Alias | Default          | Description                 |
| ------------ | ----- | ---------------- | --------------------------- |
| `ROOT`       |       | `.`              | Directory to scan for repos |
| `--when`     | `-w`  | `7d`             | Time window                 |
| `--depth`    |       | `3`              | Max search depth for repos  |
| `--provider` | `-p`  | `auto`           | AI backend                  |
| `--model`    | `-m`  | provider default | Model name                  |
| `--lang`     | `-l`  | default          | Output language             |

```bash
gitpulse dashboard ~/code --when 30d
gitpulse dashboard "C:\Users\You\Documents" --depth 2
```

While running, `dashboard` shows a live progress bar: percentage, a count of
repositories done versus total, the repository currently being analyzed, and
elapsed time. When finished, the bar disappears and the result table is printed,
followed by a one-line summary (how many repositories were active, idle, failed,
and scanned). `summary` and `digest` show a spinner for each stage they go
through (reading commits, summarizing, sending) so the terminal never looks
frozen during a model call.

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

### `gitpulse providers`

List AI backends and their availability. For Ollama, shows installed models.
Takes no options.

```bash
gitpulse providers
```

### `gitpulse config`

View or set persistent preferences. Currently the default output language.

| Option   | Alias | Description                                         |
| -------- | ----- | --------------------------------------------------- |
| `--lang` | `-l`  | Set and persist the default language (code or name) |
| `--show` |       | Show the active language and where it comes from    |

```bash
gitpulse config --lang fr
gitpulse config --show
```

The setting is saved to `~/.gitpulse/config.json`.

The five summarizing commands (`summary`, `remote`, `digest`, `dashboard`,
`watch`) also accept `--provider` / `-p`, `--model` / `-m`, and `--lang` / `-l`.

### `gitpulse cache-clear`

Delete all cached remote clones (used by `gitpulse remote`). Takes no options.

```bash
gitpulse cache-clear
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

Each summary is a single model call. GitPulse sizes its output budget to the
number of commits (`max_tokens` scales from 3,000 to 12,000) so the response is
never truncated on large repos. Every run prints a cost line reflecting the
provider used:

```
claude:claude-sonnet-4-6 · 6893+2400 tok · $0.0567
ollama:qwen2.5-coder:7b · 6893+2400 tok · free
local fallback (no model call, $0.00)
```

Ollama and local runs are free. For Claude, pricing follows the model in use;
check the Anthropic console for current rates. Use a shorter `--when` window
while testing to keep payloads small, or run `-p ollama` / `-p local` to avoid
API cost entirely.

---

## Architecture

```
gitpulse/
├── core/
│   ├── models.py       # plain dataclasses: Commit, FileChange, RepoActivity
│   ├── collector.py    # pygit2 history walk + per-file diff stats
│   ├── remote.py       # bare-clone any git URL into a cache (pygit2 + git CLI)
│   ├── dateparse.py    # --when parsing: intervals, dates, ranges, weekdays
│   ├── config.py       # language resolution + persisted preferences
│   └── changelog.py    # Conventional-Commits release notes
├── ai/
│   ├── providers.py    # Claude API + Ollama backends, auto-detection
│   └── summarizer.py   # Summary model, local fallback, provider dispatch
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
