# Changelog

## 0.2.0 (2026-10-27)

### One argument for any source

- New `core/sources.py`: a single resolver for a repository, a parent folder,
  a git URL (`https://`, `git@`, `ssh://`) or a named workspace (`@name`).
  `summary`, `log`, `standup`, `compare`, `digest`, `watch`, `risks`,
  `timesheet` and `dashboard` all go through it, and so does the web API.
- **Named workspaces** (`gitpulse workspace add|remove|list|show`) mix Windows
  folders, WSL paths, SSH repos and forge URLs. Unreachable members are
  reported and skipped, and same-named repos get distinct labels.
- `digest` and `watch` now support parent folders, workspaces, URLs and
  `--author`, like the other commands. Before, they only read a single repo.

### Projects anywhere

- `gitpulse locations` and the web Browse dialog list WSL distros (from
  Windows, with running state), Windows drives (from WSL), SSH hosts from
  `~/.ssh/config`, and saved workspaces.
- SSH browsing runs in batch mode (key or agent only), with host validation,
  and detects bare repos. A picked repo becomes an `ssh://` source.
- Fixed: the folder browser marked every subfolder of a repository as a
  repository, which was also slow over `\\wsl.localhost`.

### Trust

- Secrets are redacted before any cloud call, in digests and in commit-message
  generation (`GITPULSE_REDACT=cloud|always|off`). The cost line reports how
  many were removed.
- `summary --dry-run` prints the exact payload, the token estimate and the
  worst-case cost, and sends nothing.
- A digest cache doubles as a history: identical re-runs are free, and
  `gitpulse history list|show|clear` reopens past digests. Use `--no-cache` or
  `GITPULSE_CACHE=off` to opt out. `cache-clear --digests` deletes the history.

### Insight

- `gitpulse risks` adds deterministic risk flags: committed secrets found in
  diffs, large changes without tests, reverts, fix chains, hard-to-review
  commits, churn hotspots, off-hours work and unclear messages. `--fail-on`
  sets the CI exit code. The flags also feed the model and appear under every
  summary (CLI, web, digest Markdown).
- `gitpulse timesheet` estimates time from commit sessions per day, author and
  repo, as a table, CSV or Markdown. The web UI has a new Time tab with a CSV
  download.
- `gitpulse doctor` checks the environment and gives a fix hint for each
  problem.

### Other

- The CLI no longer crashes on legacy Windows consoles that cannot encode
  symbols such as `→` or `✓`. They are replaced instead.
- Added `.env.example` and corrected the documented default Claude model.
- The test suite isolates `~/.gitpulse` per test, so local config and the
  digest cache never leak into runs.

## 0.1.0

First release: semantic digests, workspace mode, remote and tracked repos,
standup, commit messages, trends, changelog, graph, notifiers, background
service, and the web UI.
