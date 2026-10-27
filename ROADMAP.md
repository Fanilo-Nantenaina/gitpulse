# GitPulse roadmap

_Last updated: 2026-10-27 (after v0.2)_

## Vision

Most developers no longer work in one place. Code sits on Windows drives, in
WSL distros, on a VPS, in containers and on several forges, and it is spread
across many repositories. `git log` answers "what changed" for one repo at a
time. Nothing answers **"what did I (or we) actually do, what matters in it,
and what comes next"** across all of them.

GitPulse is meant to be the **memory layer for a developer's work**: it reads
every repository you touch, wherever it lives, and turns that history into
digests, standups, reports and answers. These are written for you, for your
team, for your clients, and for the coding agents that work next to you.

### Who it is for

| Persona                        | The job GitPulse does                                                         |
| ------------------------------ | ----------------------------------------------------------------------------- |
| Freelancer / multi-client dev  | Standups and client reports across many repos, with time estimates for invoices |
| Tech lead                      | A weekly team digest, risk flags, and where effort actually went              |
| Developer starting on a repo   | A guided tour of the last months of a codebase                                |
| AI coding agent                | Project history as context, through MCP                                       |

### Principles

1. **Local-first, private by default.** Nothing leaves the machine unless you
   choose a cloud model, and then you can see exactly what is sent.
2. **Evidence over vibes.** Every claim cites commits, files or symbols. A
   summary that cannot point to its evidence is a bug.
3. **Works where the code lives.** Windows, WSL, SSH, containers and any git
   host are all first-class. No API lock-in to one forge.
4. **Model-agnostic, never model-dependent.** Claude, OpenAI, Gemini or Ollama,
   with a deterministic offline fallback that always works.
5. **One engine, several front doors.** CLI, web UI, notifications, and next an
   MCP server and an editor extension, all on the same core.

---

## Where we are: v0.2 (shipped)

v0.1 laid the base: semantic digests, workspace mode, remote and tracked repos,
standups, commit messages, trends, changelogs, the commit graph, notifiers, the
background service and the web UI.

v0.2 reorganises it around one idea, **one argument for any source**, and adds
the trust and insight layers. Details are in [CHANGELOG.md](CHANGELOG.md).

- `core/sources.py` resolves a repo, a parent folder, a git URL or a
  `@workspace`, and every command uses it
- Named workspaces spanning Windows, WSL, SSH and forges
- Project navigation beyond the local disk: WSL distros, Windows drives and
  SSH hosts
- Secret redaction, dry runs, the digest cache and saved history
- Deterministic risk flags, including committed secrets found in diffs
- Time reports from commit times, as table, CSV or Markdown
- `gitpulse doctor`

---

## Phase 1: "Everywhere" (v0.2 done, rest by December 2026)

Goal: any repo you can reach from your machine is one click or one argument
away, and it is analyzed at full speed.

- [x] Location discovery: home, drives, WSL distros (registry plus running
      state), Windows drives from inside WSL, SSH hosts with `Include` support
- [x] SSH browsing in batch mode (key/agent only), with repo and bare-repo
      detection, picked as an `ssh://` remote
- [x] **Named workspaces across locations.** Save a set such as
      `client-a = C:\work\a + \\wsl.localhost\Ubuntu\home\me\api + ssh://vps/srv/git/a.git`
      and run `gitpulse summary @client-a`. This is the feature that makes "every
      repo, everywhere" a single digest.
- [ ] **Containers and dev containers.** List running Docker/Podman containers
      that hold repos. Pull their history through a streamed `git bundle` over
      `docker exec`, which needs no git daemon and no exposed port. The same
      bundle transport also covers SSH hosts whose repos are not otherwise
      reachable.
- [ ] **SSH working-tree mode.** Run `git status` and `git diff` on the host so
      commit messages and the standup's WIP section work over SSH as well.
- [ ] **WSL fast path.** Benchmark pygit2 over `\\wsl.localhost` on large
      repos. Past a threshold, collect inside the distro through `wsl.exe -d`
      and stream the result back.
- [ ] Pinned and recent locations in the Browse dialog, with a path breadcrumb
- [x] `gitpulse doctor`: checks git, the SSH agent, WSL, providers, Ollama,
      the config dir and the caches, each with a fix hint
- [x] Ship the `.env.example` the README referenced
- [ ] `doctor --fix` for the safe cases (start ssh-agent, create the config dir)

**Exit criteria:** a digest that mixes Windows, WSL and SSH repos in one run
from a named workspace. Browsing a running distro takes under 1 s per folder.

## Phase 2: "Trust" (mostly in v0.2, rest by January 2027)

Goal: safe to point at client code and cheap to run every day.

- [x] **Secret redaction** before any cloud call. Diff excerpts are the
      main risk: tokens, keys, `.env` content, emails. Use pattern plus entropy
      detection, and report what was redacted. PII (emails, names) is still
      to do.
- [x] **"What will be sent" preview** (`summary --dry-run`): a dry run that shows the exact payload
      and its token count before a cloud run
- [ ] **Per-repo privacy policy**: mark a repo or workspace local-only, so only
      Ollama or the local fallback is used and cloud is refused with a clear
      message
- [x] **Quality-risk flags** as deterministic detectors with severity: large
      diffs without test changes, direct pushes to the default branch,
      fix-after-fix and revert chains, churn hotspots, plus committed secrets
      found in diffs. Still to add: direct pushes to the default branch, and a
      bus-factor detector.
- [x] **Summary cache** keyed on (commit range, model, language, prompt version),
      so re-running the same window is free
- [ ] **Budget guardrails**: a monthly cloud budget, an estimate before each
      run, and a warning when a run would exceed it

**Exit criteria:** a seeded-secrets test corpus never reaches a provider. A
repeated digest costs nothing.

## Phase 3: "Memory" (target: March 2027)

Goal: GitPulse remembers, so long periods become cheap and searchable.

- [x] **History store**: every model digest is saved with its window,
      provider and cost (`gitpulse history`). JSON files for now.
- [ ] Move the history to SQLite once retrospectives need queries, and add a
      timeline view in the UI
- [ ] **Hierarchical retrospectives**: monthly, quarterly and yearly reviews
      built from stored weekly digests instead of re-reading raw history. This
      is better quality on long windows and a fraction of the tokens.
- [ ] **Ask your history**: "when did we change the auth flow?" answered from
      commits and digests, with SHAs cited. Local embeddings via Ollama are
      optional, and keyword search is the default.
- [x] **Time reports**: reconstruct work sessions from commit timestamps (gap
      threshold, first-commit warm-up), per repo, workspace or client, exported
      as CSV or Markdown. Clearly labeled as estimates. Built for freelancer
      timesheets. Shipped early in v0.2 (`gitpulse timesheet`, the web Time tab).
- [ ] Time report presets per client: hourly rate, rounding, and an invoice-ready
      export
- [ ] **Repo tour** (`gitpulse tour`): the last N months of a codebase for a
      newcomer, covering main areas, who owns what, active branches and recent
      decisions

**Exit criteria:** a 12-month retrospective of a busy repo in under 30 s using
stored digests. Time reports land within ±20% of a hand-kept log on a
reference week.

## Phase 4: v0.5 "Flow" (target: April 2027)

Goal: GitPulse produces the artifacts developers write by hand every week.

- [ ] **PR descriptions** (`gitpulse pr`): branch against base, giving a title,
      summary, test notes and risk. Optionally posted to GitHub, GitLab or
      Forgejo.
- [ ] **Audience modes** for every digest: `dev` (default), `manager` (outcomes,
      no file paths) and `client` (plain language, no internal names)
- [ ] **Polished release notes** layered on the Conventional-Commits changelog,
      for developers or for customers
- [ ] **Git hook installer**: `prepare-commit-msg` uses the commit-message
      generator, with opt-in per repo
- [ ] **Issue linkage**: detect Linear, Jira and GitHub keys in branches and
      commits, then produce a "progress per ticket" digest

## Phase 5: v0.6 "Agents and integrations" (target: June 2027)

Goal: GitPulse becomes infrastructure that other tools call.

- [ ] **MCP server** (`gitpulse mcp`) with the tools `list_locations`,
      `summarize`, `log`, `standup`, `compare` and `search_history`. Coding
      agents get project history as context without shelling out.
- [ ] **Stable local HTTP API** with OpenAPI docs, and token auth whenever
      bound beyond loopback
- [ ] **VS Code extension**: digest sidebar, commit-message button and a
      standup command. It runs where the code is, so Remote-WSL, Remote-SSH and
      Dev Containers work for free.
- [ ] **Team digests**: weekly per channel with per-person sections, strictly
      opt-in per author

## Phase 6: v1.0 "Polish and distribution" (target: mid 2027)

- [ ] Distribution: PyPI release, winget and Scoop, a Homebrew tap, a signed
      Windows build of `gitpulse-gui`, and an in-app update notice
- [ ] **Frontend rebuild**: the UI is built from concatenated HTML strings.
      Move it to small components with keyboard navigation and accessibility,
      plus Playwright smoke tests in CI on all three OSes.
- [ ] **Incremental collection**: a per-repo cache of the last seen commit,
      and parallel workspace collection, so monorepos and 50-repo workspaces
      stay fast
- [ ] A docs site (the README is now 900+ lines), demo GIFs and sample reports
- [ ] Telemetry: **none**, stated explicitly

---

## Ongoing engineering health

- Keep the `core` layer free of AI, CLI and web imports. New capabilities
  (locations, history, redaction) land in `core` first.
- Every new endpoint gets a security test. The loopback/origin guard covers
  state-changing routes, and anything that spawns a process (`ssh`, `wsl.exe`,
  `docker`) validates its arguments and is never reachable through a GET.
- The CI matrix stays Windows/Linux/macOS. WSL- and SSH-specific code keeps
  pure parsing functions that are unit-tested on every OS.
- The UI's i18n covers EN and FR today. Add a language only together with its
  fallback strings for the local summary.

## Parking lot (not scheduled)

- Burnout signals from off-hours trends. Personal view only and never shared,
  which needs careful design first.
- A Gitea/Forgejo Actions or GitHub Action that posts the weekly digest as a
  discussion
- Mobile-friendly read-only digest pages served by `gitpulse service`
- Cross-repo "what broke" view: correlate reverts with the commits they undo
