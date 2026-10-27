# GitPulse

**Your git history, read for you — on every machine you work on.**

GitPulse turns commit history into a narrative, theme-grouped digest instead of
a raw `git log` dump: what the week was about, which subsystems moved, where
the risk is. It works on one repo or a whole folder of them, on your Windows
drives, inside your WSL distros, on servers you reach over SSH, and on any git
forge — and it runs local-first, with Claude, OpenAI, Gemini, a local Ollama
model, or no model at all.

What you get out of it:

- **Digests** — a synthesis, themes citing real files and symbols, and
  evidence-backed observations, in 10 languages.
- **Standups and commit messages** — yesterday's work plus today's WIP, and a
  Conventional-Commits message for your uncommitted changes.
- **Every repo, everywhere** — one argument for everything: a repo, a parent
  folder, a git URL, or a **named workspace** (`@client-a`) mixing Windows,
  WSL, SSH and forge repos. A browser reaches WSL distros, Windows drives and
  SSH hosts.
- **Safe to point at client code** — secrets are redacted before any cloud
  call, `--dry-run` shows the exact payload and cost, and identical re-runs are
  served from a local history for free.
- **Insight without a model** — deterministic risk flags (committed secrets,
  big untested changes, fix chains, reverts…) and time reports reconstructed
  from commit times, exportable as CSV for invoicing.
- **Delivery** — changelogs, Slack/Telegram/email/desktop digests, schedules
  and a background service on Windows, Linux and macOS.

Not sure your setup is complete? `gitpulse doctor` checks it and tells you what
to fix.

See [ROADMAP.md](ROADMAP.md) for where it is heading.

---

## Why it's different

Most git-stat tools count commits. GitPulse _reads_ them: it sends commit
messages, full bodies, per-file diff stats, real diff excerpts from the largest
commits, and a precomputed signals block (churn hotspots, off-hours commits,
fix/revert chains, large diffs) to a language model, which clusters the work
into themes and writes a code-review-style digest. The diff excerpts are what
let it name the actual subsystems and fields that changed, rather than
paraphrasing commit subjects. The collection layer (pygit2) is the boring part
— the value is the semantic layer on top.

The digest leads with a synthesis (a neutral Overview of what the period was
about), then detailed themes citing concrete files and symbols, then optional
observations. Observations are evidence-backed and balanced — neutral facts,
positives, or genuine risks — rather than generic advice like "may require
testing". The signals block gives the model hard facts to ground them in.

The model can be Anthropic's Claude API or a local Ollama model — GitPulse
auto-detects what's available, or you pick one explicitly. With no model at all
it still works: it falls back to a deterministic local summary (prefix grouping
plus pattern detection), so it's useful fully offline too.

A note on local models: smaller Ollama models follow the "be specific, cite
evidence" instructions less reliably than Claude or large coder models. For the
sharpest observations, prefer Claude or a large coder-tuned model
(e.g. qwen3-coder).

---

## Install

### Recommended: pipx (isolated, on your PATH, all three OSes)

[pipx](https://pipx.pypa.io) installs GitPulse into its own environment and puts
the `gitpulse` command on your PATH — no virtualenv juggling, no global clutter.

```bash
pipx install "gitpulse[all] @ git+https://github.com/<you>/gitpulse.git"
# or from a local checkout:
pipx install ".[all]"
```

After this, `gitpulse` works from any terminal, and `gitpulse-gui` launches the
desktop UI. To upgrade: `pipx upgrade gitpulse`. To remove: `pipx uninstall gitpulse`.

> **If `pipx uninstall gitpulse` fails with "file in use" / "WinError 32":** a
> running GitPulse server is holding `gitpulse.exe` locked. Run
> `gitpulse shutdown` first — it terminates every GitPulse server process
> (managed, orphaned, or whatever is holding the port) and frees the port, so
> the uninstall then succeeds. The command uses a precise match and never
> touches unrelated processes that merely mention "gitpulse".

> If `gitpulse` isn't found afterwards, run `pipx ensurepath` once and reopen
> the terminal (this adds pipx's bin dir to PATH on Windows, Linux, and macOS).

### Developer install (editable)

```bash
git clone https://github.com/<you>/gitpulse.git
cd gitpulse
pip install -e ".[all]"      # core + AI + scheduler + desktop notifications
```

Editable install (`-e`) means changes to the source take effect immediately,
without reinstalling.

### Optional dependency groups

| Extra      | Pulls in             | Needed for                |
| ---------- | -------------------- | ------------------------- |
| `ai`       | `anthropic`          | Claude semantic summaries |
| `schedule` | `apscheduler`        | `gitpulse watch`          |
| `desktop`  | `plyer`              | desktop notifications     |
| `web`      | `fastapi`, `uvicorn` | the web UI / service      |
| `dev`      | `pytest`, `httpx`    | running the test suite    |
| `all`      | runtime extras above | everything                |

Install a subset, e.g. `pip install -e ".[ai]"`, if you don't need the rest.

> **Windows note:** `pygit2` ships prebuilt wheels for most Python versions.
> If `pip install` fails on it, upgrade pip (`python -m pip install -U pip`)
> and retry, or install a Python version with an available wheel.

---

## Two ways to run it

GitPulse is one tool with two front doors — use whichever fits the moment.

**CLI** — for quick, scriptable answers in the terminal:

```bash
gitpulse summary               # this week's digest for the current repo
gitpulse commit-msg            # message for your uncommitted changes
gitpulse dashboard --remote    # activity across all tracked repos
```

**GUI** — the same features in a local web interface:

```bash
gitpulse gui                   # starts the server and opens your browser
# or, from a desktop shortcut, the `gitpulse-gui` app (no console window)
```

---

## Running in the background (service)

Two background modes, both cross-platform (Windows, Linux, macOS).

### Keep the web UI running

```bash
gitpulse service start         # launch detached, survives the terminal closing
gitpulse service status        # running / stopped + log path
gitpulse service stop
gitpulse service restart
```

This uses a PID file under `~/.gitpulse/` and needs no admin rights — handy for
"always have the UI a click away."

### Survive reboots (native OS service)

`gitpulse service install` generates the right unit for your OS and prints the
exact install commands — it never touches system files for you, so you stay in
control:

```bash
gitpulse service install web                 # keep the UI up at boot/login
gitpulse service install watch --path . --every 24h --to slack,desktop
gitpulse service install web --write ./       # write the unit file instead of printing
```

- **Linux** → a `systemd --user` service / timer (`systemctl --user enable --now …`)
- **macOS** → a `launchd` LaunchAgent plist (`launchctl load …`)
- **Windows** → a Task Scheduler `.bat` (`schtasks /Create …`, run at logon)

The `web` kind keeps the UI server alive; the `watch` kind sends a periodic
digest to your chosen channels.

---

## Configuration

GitPulse reads secrets from **environment variables**. Copy
[`.env.example`](.env.example) to `.env` for reference, or set system variables
directly. Preferences (language, tracked remotes, named workspaces, keys pasted
in the web UI) live in `~/.gitpulse/config.json`, outside any repository.

### Persisting variables on Windows (PowerShell)

```powershell
[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")
```

Restart the terminal afterwards so the variable is picked up.

### All variables

| Variable                    | Purpose                                     | Default                  |
| --------------------------- | ------------------------------------------- | ------------------------ |
| `ANTHROPIC_API_KEY`         | Enables the Claude provider                 | —                        |
| `ANTHROPIC_WORKSPACE_ID`    | Workspace id, if your Claude key needs one  | —                        |
| `GITPULSE_MODEL`            | Claude model                                | `claude-opus-5`          |
| `GITPULSE_LANG`             | Default output language (code or name)      | `en`                     |
| `GITPULSE_GIT_TOKEN`        | Access token for private HTTPS remotes      | —                        |
| `OPENAI_API_KEY`            | Enables the OpenAI provider                 | —                        |
| `GEMINI_API_KEY`            | Enables the Gemini provider                 | —                        |
| `GITPULSE_GIT_USERNAME`     | Username for token auth                     | `git`                    |
| `GITPULSE_SSH_KEY`          | Path to private SSH key for SSH remotes     | agent                    |
| `GITPULSE_SSH_PASSPHRASE`   | Passphrase for the SSH key, if any          | —                        |
| `GITPULSE_CACHE_DIR`        | Where remote clones are cached              | `~/.gitpulse/remotes`    |
| `GITPULSE_CONFIG_DIR`       | Config, workspaces and history location     | `~/.gitpulse`            |
| `GITPULSE_HISTORY_DIR`      | Where saved digests (the cache) are kept    | `<config dir>/history`   |
| `GITPULSE_CACHE`            | `off` disables the digest cache             | on                       |
| `GITPULSE_REDACT`           | `cloud`, `always` or `off` (see Privacy)    | `cloud`                  |
| `GITPULSE_ALLOWED_HOSTS`    | Extra hostnames the web UI answers to       | —                        |
| `OLLAMA_HOST`               | Ollama server URL                           | `http://localhost:11434` |
| `GITPULSE_OLLAMA_MODEL`     | Default Ollama model (else auto-picked)     | —                        |
| `GITPULSE_OLLAMA_MAX_CTX`   | Ceiling for the Ollama context window       | `32768`                  |
| `GITPULSE_SLACK_WEBHOOK`    | Slack incoming webhook URL                  | —                        |
| `GITPULSE_DISCORD_WEBHOOK`  | Discord webhook URL                         | —                        |
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

| Provider         | Requires                                        | Cost                                                                        |
| ---------------- | ----------------------------------------------- | --------------------------------------------------------------------------- |
| `claude`         | `ANTHROPIC_API_KEY` + `anthropic` package       | paid (per token)                                                            |
| `openai`         | `OPENAI_API_KEY`                                | paid (per token)                                                            |
| `gemini`         | `GEMINI_API_KEY`                                | paid (per token)                                                            |
| `ollama`         | a running Ollama server with at least one model | free, local, offline                                                        |
| `local`          | nothing                                         | free; deterministic, no model                                               |
| `auto` (default) | —                                               | picks the first available: ollama (free) first, then claude, openai, gemini |

API keys can be set as environment variables, or pasted into the web UI's
provider manager (stored in the local config file, not system-wide). The cloud
providers (claude, openai, gemini) call their HTTP APIs directly. Run
`gitpulse providers` to see each backend's status and why it's unavailable:

```bash
gitpulse providers
```

### Using Ollama

Install Ollama, pull a model, and GitPulse finds it automatically:

```bash
ollama pull llama3.1            # or qwen2.5-coder, mistral, etc.
gitpulse summary -p ollama      # auto-picks an installed model
gitpulse summary -p ollama -m qwen2.5-coder:7b
```

If `--model` is omitted, GitPulse picks among your installed models, preferring
ones that answer directly over "thinking" models (which follow a strict JSON
schema less reliably) and skipping embedding-only models, which cannot write
text at all. Set `GITPULSE_OLLAMA_MODEL` to pin one. A non-default server
location can be set with `OLLAMA_HOST`.

Coder-tuned models (qwen2.5-coder, deepseek-coder) tend to produce the best
commit summaries. Quality is lower than Claude but the run is free and offline.

**Context window.** Ollama's own default context is small and it silently
discards any prompt beyond it — a digest sent to it would be written from a
fragment of your history. GitPulse therefore sets `num_ctx` per request, sized
to the payload and capped by both the model's limit and
`GITPULSE_OLLAMA_MAX_CTX` (32k by default, since a large window costs real
memory). Raise it if you analyze long windows on a machine that can afford it.

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

## Privacy, cost and history

**Secret redaction.** Before a payload leaves your machine for a cloud model,
GitPulse scrubs it: private keys, AWS/GitHub/GitLab/Slack/Stripe/Google/
OpenAI/Anthropic tokens, JWTs, credentials embedded in URLs, and high-entropy
values assigned to names like `password`, `secret`, `token` or `api_key`. Each
one becomes `[REDACTED:<kind>]`, and the cost line says how many were removed
(`· 2 secret(s) redacted`). Ordinary code such as `token = os.environ["TOKEN"]`
is left alone. `GITPULSE_REDACT=always` also scrubs local (Ollama) payloads;
`off` disables it. The same applies to commit-message generation.

**Dry run.** `gitpulse summary --dry-run` prints the system prompt, the exact
payload after redaction, the token estimate and the worst-case cost for the
selected provider, and sends nothing.

**Digest cache and history.** Every successful model digest is saved under
`~/.gitpulse/history`, keyed on the provider, model, language, prompt and
payload. Running the same window again, from the CLI or the web UI, returns the
saved digest instantly (`· cached · $0.00`); new commits, another model or
another language produce a fresh one. `--no-cache` forces a new call and
`GITPULSE_CACHE=off` disables caching entirely.

```bash
gitpulse history list            # what GitPulse has already written
gitpulse history show 1          # reopen one, by row number or key prefix
gitpulse history clear
```

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

## Several repositories at once

Point GitPulse at a **parent folder** instead of a repository and it finds the
git repos underneath, then reports on all of them together. Nothing to
configure and no separate command: if the path you give is a repo it behaves
exactly as before, and if it is a folder of repos it switches to workspace
mode on its own.

```bash
gitpulse summary ~/code                  # every repo under ~/code, merged
gitpulse log ~/code --when yesterday
gitpulse standup ~/code
gitpulse compare ~/code
```

The digest stays aware that these are separate projects: each commit is
tagged with its repository, themes are organised per repo unless an effort
genuinely spans several, and the synthesis says where the effort concentrated
and which repos were quiet. Identically-named files do not merge — a dozen
`README.md` files stay a dozen entries, not one giant hotspot.

`--depth` controls how far down the scan goes (default 3). Nested repos inside
a checkout are skipped, so vendored copies and submodules are not
double-counted.

### Filtering by author across repos

The author list is aggregated over every repo, showing who works where.
Selecting an author narrows the report to the repos that person actually
worked in — and `--author-scope` decides what "worked in" means:

| Scope              | Keeps                                                 |
| ------------------ | ----------------------------------------------------- |
| `window` (default) | repos where they committed **inside the time window** |
| `all`              | every repo they have **ever** committed to            |

`window` keeps the numbers tight: every repo listed has real content. `all`
answers a different question — "which of their projects have gone quiet?" —
by keeping repos they own but did not touch this period, shown with zero
commits.

```bash
gitpulse summary ~/code --author alice@example.com                       # active this period
gitpulse summary ~/code --author alice@example.com --author-scope all    # + her quiet repos
```

In the web UI the same control sits next to the author picker.

Graph and commit-message generation stay single-repo: one shows a single
commit DAG, the other needs one working tree.

---

## Projects anywhere: WSL, Windows drives, SSH hosts

Like an editor's remote explorer, GitPulse can reach projects that do not live
on the filesystem it runs on. Run `gitpulse locations` to see every place it
can browse from where it is running, with the exact path to paste:

| Running on | It also lists                         | How it reaches them                          |
| ---------- | ------------------------------------- | -------------------------------------------- |
| Windows    | every WSL distro (running or stopped) | `\\wsl.localhost\<distro>\…` UNC paths       |
| WSL        | the Windows drives                    | `/mnt/c`, `/mnt/d`, …                        |
| anywhere   | the hosts in `~/.ssh/config`          | `ssh` (key/agent auth), analyzed as a remote |

**WSL from Windows.** A WSL folder is an ordinary path, so every command works
on it, workspace mode included:

```powershell
gitpulse summary \\wsl.localhost\Ubuntu-26.04\home\me\code   # all repos in WSL ~/code
gitpulse standup \\wsl.localhost\Ubuntu-26.04\home\me\api
```

GitPulse finds distros from the registry (no distro is started just to list
them) and asks `wsl.exe` which are running. A running distro opens on its home
folder; opening a stopped one boots it, which takes a few seconds. Docker
Desktop's internal distros are hidden.

**Windows from WSL.** Mounted drives (`/mnt/c`, …) are listed, so a GitPulse
installed inside WSL can reach checkouts kept on the Windows side.

**SSH hosts.** Hosts declared in `~/.ssh/config` (including `Include` files;
wildcard patterns are skipped) appear in the list. Browsing a host runs a
read-only listing over `ssh` in batch mode — key or agent auth only, never a
password prompt — and marks the folders that are git repositories, bare ones
included. Picking one gives an `ssh://host/path` URL, which goes through the
same cached bare clone as `gitpulse remote`:

```bash
gitpulse remote ssh://vps/srv/git/api.git -w last-week
```

A host you have never connected to must be accepted once with `ssh <host>` in a
terminal, since batch mode refuses unknown host keys. Commit-message generation
and the standup's WIP section need a working tree, so they apply to local and
WSL folders, not to SSH picks.

In the web UI all of this lives in the **Browse** dialog: locations are grouped
as This PC, WSL, Windows and SSH above the folder list, a green dot marks
running distros, a field accepts any `user@host` that is not in your SSH
config, and a **Use** button on each repository picks it without opening it.

---

## Named workspaces

A named workspace is a saved list of repos, parent folders and git URLs, from
any location. Every command that takes a `PATH` accepts it as `@name`, and the
result is one digest that stays aware of each repo:

```bash
gitpulse workspace add client-a C:\work\client-a \\wsl.localhost\Ubuntu\home\me\api ssh://vps/srv/git/infra.git
gitpulse workspace show client-a      # resolves every member, lists failures
gitpulse summary @client-a -w last-week
gitpulse timesheet @client-a -w last-month -f csv > client-a.csv
gitpulse workspace remove client-a ssh://vps/srv/git/infra.git
```

Members that cannot be reached (a stopped VPS, a moved folder) are reported and
skipped, not fatal. Two repos with the same name get distinct labels (`api`,
`api-2`). In the web UI, saved workspaces are the first group of the Browse
dialog, and its **+ Workspace** button adds the folder or SSH repo you are
looking at to a workspace.

---

## Risk flags

`gitpulse risks` runs deterministic detectors over a window, with no model and
no cost:

| Flag                        | Severity | Fires when                                                               |
| --------------------------- | -------- | ------------------------------------------------------------------------ |
| Possible secret committed   | high     | an added diff line matches a secret pattern (the value is never printed) |
| Large change without tests  | medium   | 400+ changed lines in code files and no test file touched                |
| Reverted work               | medium   | revert commits in the window                                             |
| Repeated fixes in one file  | medium   | the same file appears in 3+ `fix` commits                                |
| Hard-to-review commit       | low      | 40+ files or 2000+ lines, lockfiles excluded                             |
| Churn hotspot               | low      | one file changes in 5+ commits and 25%+ of them                          |
| Lots of off-hours work      | low      | 30%+ of commits between 22h and 6h                                       |
| Unclear commit messages     | low      | 3+ subjects like `wip`, `tmp`, `fixup!`                                  |

The same flags appear under every `summary` (CLI and web) and in `digest`
Markdown, and they are passed to the model as verified facts so its
observations cite them instead of guessing. `--fail-on high` exits with code 2
when such a flag exists, which makes it usable in CI or a pre-push hook:

```bash
gitpulse risks . -w 30d
gitpulse risks @client-a -w 7d --fail-on high
```

---

## Time reports

`gitpulse timesheet` reconstructs work sessions from commit timestamps across
all branches. A session ends after `--gap` minutes without a commit (default
120), and each session is credited `--warmup` minutes for the work before its
first commit (default 30). A session that spans several repos is split between
them by commit share, so time is never counted twice.

```bash
gitpulse timesheet                         # this week, current repo
gitpulse timesheet @client-a -w last-month --author me@example.com
gitpulse timesheet ~/code -w 2026-10-01..2026-10-31 -f csv > october.csv
gitpulse timesheet . -f md                 # Markdown table for a report
```

These are estimates: work that never reached a commit is invisible, so treat
the numbers as a floor and a sanity check for invoices, not as a time tracker.
The web UI's **Time** tab shows the same report with a CSV download.

---

## Web interface

If you'd rather click than remember commands, GitPulse ships a local web UI
covering every feature:

```bash
pip install -e ".[web]"     # or ".[all]"
gitpulse serve              # opens your browser at http://127.0.0.1:8420
```

It runs entirely on your machine (no data leaves it).

**One context, every view.** The bar at the top holds the repository and three
global filters: period, branches and authors. Summary, Log, Graph, Compare and
Time all read the same selection, and they mean the same thing everywhere. For
example, "all branches" is every local branch, remote-tracking branch, tag and
HEAD, as with `git log --branches --remotes --tags HEAD`. Periods are matched on
the author date, so a rebase does not move a week of work to the day it was
rebased. A filter that a view does not use is dimmed. The Graph uses period and
authors to highlight commits rather than hide them, so the history stays whole.
The address bar keeps the view and every filter, so a link reopens the same
screen and Back/Forward move between views.

The views:

- **Summary**: KPIs and charts, then risk flags, update as soon as a filter
  changes. The AI summary runs only when you ask, with a warning before a cloud
  call on a slow or metered link, a timer and a Cancel button.
- **Log**: commits grouped by day, with a text filter. Click a commit for its
  files and diffs.
- **Graph**: an IDE-style commit graph (see [the graph](#the-commit-graph)).
- **Compare**: the current period against the average of the previous ones.
- **Time**: estimated work sessions, by day, author and repository, with CSV
  export.
- **Standup**: yesterday's work and today's context.
- **Commit**: uncommitted changes with their diffs, and an AI commit message.
- **Dashboard** and **Tracked**: activity across tracked remotes. These load
  only on demand, because every remote is fetched.
- **Settings**: providers with their live status, API keys, Ollama start,
  default model and summary language, theme and interface language.

Also built in:

- a repository picker for a path, a URL or a `@workspace`, with a folder
  browser that reaches WSL distros, Windows drives and SSH hosts;
- recent repositories;
- `Ctrl K` command palette, number keys `1`…`7` for views, `R` to refresh;
- English and French, and dark and light themes.

Refresh fetches remotes immediately. Otherwise the server reuses a fetch for 5
minutes (`GITPULSE_REMOTE_TTL`, in seconds), so moving between views on a
metered connection does not hit the network each time.

### The commit graph

The Graph view follows the conventions of IDE graph tools such as Git Graph for
VS Code:

- commits in date order, with parents always below their children;
- one line per parent link, joining the parent at its node;
- a branch's first-parent chain keeps one lane and one colour;
- lanes shift left as space frees up;
- branches, remote branches, tags and a detached HEAD as distinct badges, with
  a local branch and its remote twin on the same commit sharing one badge;
- a dashed "Uncommitted changes" row above HEAD.

It loads 300 commits, then more as you scroll, and only the visible rows are
rendered. If the repository changes between two pages, the graph reloads
instead of joining two different histories. `Ctrl F` searches messages,
authors, hashes and ref names; `/regex/` is accepted. The arrow keys move the
selection and `Esc` closes the commit panel. The panel shows author and commit
dates, clickable parents, and every changed file with its diff. A merge is
shown against its first parent.

`gitpulse serve` options: `--port` (default 8420), `--host`, `--no-open`.

## Commands

Run `gitpulse --help` for the index, or `gitpulse <command> --help` for any
single command.

Options belong to a command, not to `gitpulse` itself. Write
`gitpulse summary --provider ollama`, not `gitpulse --provider ollama`.

### `gitpulse summary [PATH]`

Print an AI semantic summary of recent activity to the terminal: a headline, an
Overview paragraph synthesizing the period, themes grouping related commits, and
optional evidence-backed observations (neutral facts, positives, or risks, not
just criticism). Also shows a 24-hour productivity sparkline and a cost line.

| Option       | Alias | Default          | Description                               |
| ------------ | ----- | ---------------- | ----------------------------------------- |
| `PATH`       |       | `.`              | Repo, parent folder, git URL, or `@workspace` |
| `--when`     | `-w`  | `7d`             | Time window (see above)                   |
| `--branch`   | `-b`  | HEAD             | Specific branch to analyze                |
| `--author`   | `-a`  | all              | Only these authors (repeatable)           |
| `--provider` | `-p`  | `auto`           | AI backend: auto, claude, ollama, local   |
| `--model`    | `-m`  | provider default | Model name                                |
| `--lang`     | `-l`  | default          | Output language (code or name)            |
| `--dry-run`  |       | off              | Show payload + cost estimate, send nothing |
| `--no-cache` |       | off              | Ignore saved digests, call the model again |
| `--no-risks` |       | off              | Skip risk detection                       |

```bash
gitpulse summary
gitpulse summary "C:\path with spaces\repo" --when 24h
gitpulse summary ~/proj -b develop -w last-week
gitpulse summary https://github.com/org/project.git -w 30d
gitpulse summary @client-a --dry-run -p claude
```

Every command below that takes a `PATH` (`log`, `standup`, `compare`, `digest`,
`watch`, `risks`, `timesheet`, and `dashboard` in local mode) accepts the same
four forms.

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

### `gitpulse standup [PATH]`

Generate a daily standup: an AI summary of yesterday's commits ("Yesterday"),
plus an inferred "Today" section from the repo state — the current branch, any
uncommitted work in progress, and other recently active branches. If yesterday
was Sunday or Monday, it looks back to the last working day (Friday) instead.

| Option       | Alias | Default          | Description     |
| ------------ | ----- | ---------------- | --------------- |
| `PATH`       |       | `.`              | Repository path |
| `--provider` | `-p`  | `auto`           | AI backend      |
| `--model`    | `-m`  | provider default | Model name      |
| `--lang`     | `-l`  | default          | Output language |

```bash
gitpulse standup
gitpulse standup "C:\Users\LEGION\Documents\Sage100 ERP\Sage100-vps" -l fr
```

### `gitpulse commit-msg [PATH]`

Generate a commit message from your uncommitted changes. Reads the diff and
produces a Conventional Commits subject line (one line, imperative) plus a
bullet-point body summarizing each change. By default it covers all changes
(staged, unstaged, and untracked); `--staged` restricts it to the index.

In the web UI this lives inside the **Standup** tab: whenever the selected local
repo has uncommitted work, a "Commit message" section appears with a staged/all
toggle, a generate button, the editable result, a copy button, and the list of
changed files with +/- counts.

| Option       | Alias | Default          | Description                        |
| ------------ | ----- | ---------------- | ---------------------------------- |
| `PATH`       |       | `.`              | Repository path                    |
| `--staged`   |       | off              | Only staged changes (default: all) |
| `--provider` | `-p`  | `auto`           | AI backend                         |
| `--model`    | `-m`  | provider default | Model name                         |
| `--lang`     | `-l`  | default          | Output language                    |

```bash
gitpulse commit-msg
gitpulse commit-msg --staged -l fr
```

### `gitpulse compare [PATH]`

Compare the current period against the average of several prior periods, to see
whether your pace is rising or falling. Reports commits, lines added/deleted,
files touched, and active days, each with the percentage change and an up/down
arrow. No AI call, no cost.

| Option      | Alias | Default | Description                       |
| ----------- | ----- | ------- | --------------------------------- |
| `PATH`      |       | `.`     | Repository path                   |
| `--period`  | `-w`  | `7d`    | Length of each period             |
| `--periods` | `-n`  | `4`     | How many prior periods to average |
| `--branch`  | `-b`  | HEAD    | Specific branch                   |

```bash
gitpulse compare                       # this week vs the prior 4 weeks
gitpulse compare --period 30d -n 3     # this month vs the prior 3 months
```

### `gitpulse remote <URL>`

Analyze a repository hosted anywhere, without cloning it yourself first. Works
with any git host — GitHub, GitLab, Forgejo/Gitea, Bitbucket, Codeberg, a
self-hosted git server — because it uses the standard git protocol, not any
host-specific API. The repo is cloned bare (history only, no working files)
into a local cache and refreshed on each run.

| Option                          | Alias | Default   | Description                                       |
| ------------------------------- | ----- | --------- | ------------------------------------------------- |
| `URL`                           |       | required  | Git URL, HTTPS or SSH                             |
| `--when`                        | `-w`  | `7d`      | Time window                                       |
| `--branch`                      | `-b`  | HEAD      | Specific branch                                   |
| `--view`                        |       | `summary` | `summary` (AI) or `log` (plain listing)           |
| `--files`                       | `-f`  | off       | In log view, list files per commit                |
| `--token`                       |       | env       | Access token for private HTTPS repos              |
| `--username`                    |       | `git`     | Username for token auth                           |
| `--ssh-key`                     |       | agent     | Path to a private SSH key                         |
| `--no-refresh`                  |       | off       | Use the cached clone, skip fetching               |
| `--insecure`                    |       | off       | Disable SSL cert verification (see warning below) |
| `--provider` `--model` `--lang` |       |           | Same as `summary`                                 |

Authentication, two ways, both configurable:

- **HTTPS + token** — pass `--token`, or set `GITPULSE_GIT_TOKEN` (and
  optionally `GITPULSE_GIT_USERNAME`). The token is injected into the fetch URL
  and never written to disk.
- **SSH** — use an SSH URL (`git@host:org/repo.git`). GitPulse uses your SSH
  agent by default, or a specific key via `--ssh-key` / `GITPULSE_SSH_KEY`
  (passphrase via `GITPULSE_SSH_PASSPHRASE`).

```bash
gitpulse remote https://github.com/org/project.git -w last-week
gitpulse remote git@forgejo.example.com:team/dataven.git -w 7d
gitpulse remote https://gitlab.com/org/repo.git --token ghp_xxx -p ollama
gitpulse remote https://codeberg.org/user/app.git --view log --files
```

Under the hood it tries pygit2 first and falls back to the system `git`
command, so SSH and HTTPS work even where pygit2 lacks transport support.
Clear the cache with `gitpulse cache-clear`.

**`--insecure` / "Allow insecure SSL".** If the server's certificate has
expired or is self-signed, the clone fails with a cert error. `--insecure`
(CLI) or the checkbox in the web UI disables SSL verification so you can keep
working. This is a workaround, not a fix: it removes protection against
man-in-the-middle attacks, so use it only on trusted networks. The real fix is
to renew the certificate server-side (e.g. Let's Encrypt). In the web UI a
warning is shown whenever it's enabled.

### `gitpulse digest [PATH]`

Generate the AI summary as Markdown and dispatch it to notification channels.

| Option     | Alias | Default   | Description                         |
| ---------- | ----- | --------- | ----------------------------------- |
| `PATH`     |       | `.`       | Repo, folder, git URL or @workspace |
| `--when`   | `-w`  | `7d`      | Time window                         |
| `--to`     |       | `desktop` | Channel; repeatable                 |
| `--author` | `-a`  | all       | Only these authors (repeatable)     |
| `--depth`  |       | `3`       | Folder scan depth                   |

The Markdown includes the medium and high risk flags.

```bash
gitpulse digest --to slack
gitpulse digest ~/proj --when 7d --to slack --to email
```

If no channel succeeds (e.g. none configured), the Markdown is printed to the
terminal as a fallback.

### `gitpulse dashboard [ROOT]`

Aggregated activity across many repositories in one table, ranked by commit
count. Two modes:

- **Local** (default): scans a directory for cloned repos.
- **Remote** (`--remote`): analyzes your tracked remote repos (see
  `track` below), fetching each into the cache first. Works with any git host.

By default the table shows metrics only (commits, lines, files) — fast and
free, which matters when analyzing 10-15 repos. Add `--summarize` to include an
AI headline per repo (one model call each, so slower and possibly billed).

| Option                          | Alias | Default | Description                                   |
| ------------------------------- | ----- | ------- | --------------------------------------------- |
| `ROOT`                          |       | `.`     | Directory to scan (local mode)                |
| `--when`                        | `-w`  | `7d`    | Time window                                   |
| `--depth`                       |       | `3`     | Max search depth (local mode)                 |
| `--remote`                      |       | off     | Use tracked remotes instead of a local folder |
| `--summarize`                   |       | off     | Add an AI headline per repo                   |
| `--no-refresh`                  |       | off     | (remote) use cached clones, skip fetch        |
| `--provider` `--model` `--lang` |       |         | Used only with `--summarize`                  |

```bash
gitpulse dashboard ~/code --when 30d              # local folder
gitpulse dashboard --remote -w 7d                 # tracked remotes, metrics
gitpulse dashboard --remote -w 7d --summarize     # + AI headline per repo
```

While running, `dashboard` shows a live progress bar: percentage, repos done
versus total, the repo currently being processed, and elapsed time. When
finished, the table is printed with a one-line summary (active, idle, failed,
total, plus total commits across all repos).

### `gitpulse track <URL>`

Add a remote repository to the tracked list used by `dashboard --remote`. Any
git URL, any host. Use `--label` to give it a friendly name in the table.

```bash
gitpulse track https://github.com/org/dataven.git --label dataven
gitpulse track git@forgejo.example.com:me/portfolio.git
```

### `gitpulse untrack <URL-or-label>`

Remove a repository from the tracked list, by URL or by label.

```bash
gitpulse untrack dataven
```

### `gitpulse tracked`

List all tracked remotes. Takes no options.

```bash
gitpulse tracked
```

Authentication for tracked private repos uses the same environment variables as
`remote`: `GITPULSE_GIT_TOKEN` (HTTPS) or your SSH key/agent.

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

### `gitpulse locations`

List every place GitPulse can browse from where it runs: home, drives, WSL
distros (on Windows, with running/stopped state), Windows drives (inside WSL),
and SSH hosts from `~/.ssh/config`, each with the path or URL to pass to other
commands. `--no-ssh` skips the SSH hosts.

```bash
gitpulse locations
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

The summarizing commands (`summary`, `remote`, `standup`, `digest`, `dashboard`,
`watch`) also accept `--provider` / `-p`, `--model` / `-m`, and `--lang` / `-l`.
`compare` is metrics-only (no AI).

### `gitpulse cache-clear`

Delete all cached remote clones (used by `gitpulse remote` and URL sources).
`--digests` also deletes the saved digests.

```bash
gitpulse cache-clear
gitpulse cache-clear --digests
```

### `gitpulse risks [PATH]`

Deterministic risk flags for a window (default `30d`). See
[Risk flags](#risk-flags). Options: `--when`, `--branch`, `--author`,
`--depth`, `--no-secrets` (skip the diff scan), `--fail-on high|medium|low`.

### `gitpulse timesheet [PATH]`

Estimated time per day, author and repo (default window `this-week`). See
[Time reports](#time-reports). Options: `--when`, `--author`, `--depth`,
`--gap`, `--warmup`, `--format table|csv|md`.

### `gitpulse workspace add|remove|list|show`

Manage [named workspaces](#named-workspaces). `add NAME MEMBER...` creates or
extends one, `remove NAME [MEMBER...]` drops members or the whole workspace,
`list` prints them, and `show NAME` resolves every member (`--no-refresh` skips
fetching URL members).

### `gitpulse history list|show|clear`

Saved digests: `list` (`-n` to limit), `show <#|key>` to reopen one, `clear`.

### `gitpulse doctor`

Checks Python, pygit2/libgit2, the git CLI, the SSH client and agent, WSL, the
config directory, caches, the web extra and every AI provider. Each problem
comes with a fix hint, and the exit code is 1 if a check fails.

```bash
gitpulse doctor
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
| `discord`  | `GITPULSE_DISCORD_WEBHOOK`                                   | Discord channel webhook URL.              |
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
number of commits (`max_tokens` scales from 4,000 to 16,000) so the response is
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
│   ├── stats.py        # chart data: per day, per author, per hour, top files
│   ├── refs.py         # what a branch selection covers, for every view
│   ├── gitgraph.py     # commit graph layout (lanes, segments), paged walks
│   ├── commitinfo.py   # files and per-file diff of one commit (or the worktree)
│   ├── diffstage.py    # working-tree changes for commit messages
│   ├── remote.py       # bare-clone any git URL into a cache (pygit2 + git CLI)
│   ├── trends.py       # period-over-period comparison metrics
│   ├── standup.py      # yesterday's work + today context (branches, WIP)
│   ├── dateparse.py    # --when parsing: intervals, dates, ranges, weekdays
│   ├── config.py       # language, preferences, tracked-remotes list
│   ├── sources.py      # one resolver: path, parent folder, git URL, @workspace
│   ├── workspace.py    # merged multi-repo activity over a resolved source
│   ├── locations.py    # browsable places: drives, WSL distros, SSH hosts
│   ├── scrub.py        # secret redaction before cloud calls
│   ├── history.py      # digest cache + saved history
│   ├── risks.py        # deterministic risk flags (incl. committed secrets)
│   ├── timesheet.py    # work sessions and time reports from commit times
│   ├── doctor.py       # environment checks
│   └── changelog.py    # Conventional-Commits release notes
├── ai/
│   ├── providers.py    # Claude, OpenAI, Gemini, Ollama backends, auto-detection
│   ├── summarizer.py   # Summary model, local fallback, provider dispatch
│   └── commitmsg.py    # Conventional-Commits message from uncommitted changes
├── cli/
│   ├── _shared.py          # shared Typer app, console, help strings, helpers
│   ├── main.py             # thin entry point: imports command modules
│   ├── commands_analyze.py # summary, log, standup, commit-msg, compare, digest
│   ├── commands_remote.py  # remote, track, untrack, tracked, cache-clear
│   ├── commands_dashboard.py  # dashboard (local scan + remote)
│   ├── commands_tools.py   # serve, changelog, watch, config, locations, providers, dates
│   ├── commands_insights.py  # risks, timesheet, doctor, history
│   ├── commands_workspace.py # workspace add/remove/list/show
│   └── render.py           # Rich terminal, git-log view, Markdown output
├── scheduler/
│   └── runner.py       # APScheduler + systemd-timer unit generation
├── service/
│   ├── controller.py   # detached web server: start/stop/status, shutdown
│   └── units.py        # systemd / launchd / Task Scheduler unit generation
├── notifiers/
│   └── dispatch.py     # slack / telegram / email / desktop
└── web/
    ├── server.py       # thin app assembly: mounts routers, serves frontend
    ├── schemas.py      # Pydantic request models
    ├── serializers.py  # dataclass → dict serializers + source resolution
    ├── browse.py       # server-side folder picker
    ├── routes/
    │   ├── analysis.py    # summary, log, compare, standup, graph, dashboard
    │   ├── commit.py      # changes-count, commit-message
    │   ├── providers.py   # provider status, latency, keys, ollama control
    │   └── repos.py       # branches, browse, locations, ssh browse, tracked, config
    └── static/         # built web UI (generated from frontend/, do not edit)
frontend/               # Svelte 5 + TypeScript sources of the web UI
├── src/lib/            # API client, app state, routing, graph geometry, i18n
├── src/components/     # context bar, pickers, commit panel, charts, dialogs
└── src/views/          # one component per view
```

The `core` layer has zero AI/CLI dependencies — import the collector in any
other tool. The `ai` and `notifiers` layers are optional extras. The web layer
is split into domain routers so each slice of the API stays small and testable.

---

## Testing

GitPulse ships a pytest suite that locks the behavior of the core logic and the
web API. `tests/test_gitgraph.py` checks the commit graph against git itself:
every line drawn from a commit is followed row by row and must land on one of
its real parents (`git rev-parse <sha>^@`), the commit set must equal
`git rev-list --branches --remotes --tags HEAD`, and lines may not merge,
vanish, change colour or cross a commit on the way. Scenarios cover merges of
several active branches, octopus and criss-cross merges, unrelated roots,
skewed dates, tags, detached HEAD, remote-tracking branches, shallow clones,
pagination and seeded random histories.

```bash
pip install -e ".[web,dev]"
pytest
```

The web UI lives in `frontend/` (Svelte 5, TypeScript, Vite). The built bundle
is committed in `gitpulse/web/static`, so installing GitPulse never needs Node.
To work on the UI:

```bash
cd frontend
npm install
npm run dev     # hot reload on :5173, API proxied to `gitpulse serve` on :8420
npm run check   # svelte-check (strict TypeScript)
npm test        # unit tests: routing, graph geometry, search, i18n
npm run build   # writes gitpulse/web/static (commit the result)
```

CI fails if the committed bundle does not match the sources.

The fixtures build real disposable git repositories with fixed commit dates, so
date-window, graph, and diff assertions are deterministic.

---

## Roadmap

Shipped in 0.2: named workspaces across locations, one source resolver for
every command, secret redaction, dry runs, the digest cache and history, risk
flags, time reports, `doctor`, and browsing across WSL, Windows drives and SSH
hosts. See [CHANGELOG.md](CHANGELOG.md).

Next up: containers and an SSH working-tree mode, hierarchical retrospectives
built on the history, PR descriptions and audience modes, and an MCP server so
coding agents can ask GitPulse what happened. The full plan is in
[ROADMAP.md](ROADMAP.md).

---

## License

MIT — see [LICENSE](LICENSE).
